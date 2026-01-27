"""Reasoning model client for task planning and decision making.

The reasoning model is a text-only LLM that:
- Decides the next action based on current observation
- Handles errors and decides recovery strategies
- Does NOT process images (uses VisionClient's observation instead)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from app.core.llm.base import BaseLLMClient

if TYPE_CHECKING:
    from app.domain.agent.entities import Action, AgentContext, Observation, Step

logger = logging.getLogger(__name__)


class ReasoningClient(BaseLLMClient):
    """Reasoning model client for decision making.

    This client uses a text-only LLM (e.g., qwen-plus, gpt-4) to:
    1. Decide the next action based on screen observation
    2. Handle errors and plan recovery
    3. Determine when a task is complete or has failed
    """

    async def decide_action(
        self,
        observation: "Observation",
        goal: str,
        history: list["Step"],
        available_apps: Optional[list[str]] = None,
        loop_hint: Optional[str] = None,
    ) -> "Action":
        """Decide the next action based on current observation.

        Args:
            observation: Current screen observation from VisionClient
            goal: The task goal to achieve
            history: List of previous steps (observation -> action -> result)
            available_apps: List of installed app package names
            loop_hint: Optional hint when loop is detected

        Returns:
            Action to execute next
        """
        from app.domain.agent.entities import Action
        from app.domain.agent.prompts.reasoning import ACTION_DECISION_PROMPT

        # Format history for prompt
        history_text = self._format_history(history)

        # Format observation
        observation_text = self._format_observation(observation)

        # Build prompt
        prompt = ACTION_DECISION_PROMPT.format(
            goal=goal,
            observation=observation_text,
            history=history_text,
            available_apps=", ".join(available_apps) if available_apps else "未知",
        )

        # Add loop detection hint if present
        if loop_hint:
            prompt += f"\n\n## ⚠️ 循环警告\n{loop_hint}"
            logger.warning(f"Loop hint added to prompt: {loop_hint}")

        logger.debug(f"Reasoning model prompt: {prompt}")

        # Call LLM
        messages = [{"role": "user", "content": prompt}]
        response = await self._call_llm(messages, json_response=True)

        logger.info(f"Reasoning model response: {response.content}")

        # Parse response
        try:
            data = self.parse_json_response(response.content)
            return Action.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to parse action response: {e}, content: {response.content[:200]}")
            # Return a fail action on parse error
            from app.domain.agent.entities import ActionType
            return Action(
                action_type=ActionType.FAIL,
                target=None,
                parameters={},
                reasoning=f"无法解析模型响应: {e}",
            )

    async def handle_error(
        self,
        error: str,
        context: "AgentContext",
        last_action: Optional["Action"] = None,
    ) -> "Action":
        """Handle an error and decide recovery strategy.

        Args:
            error: Error message from the failed action
            context: Current agent context
            last_action: The action that failed (if any)

        Returns:
            Recovery action to try
        """
        from app.domain.agent.entities import Action
        from app.domain.agent.prompts.reasoning import ERROR_RECOVERY_PROMPT

        # Build prompt
        prompt = ERROR_RECOVERY_PROMPT.format(
            goal=context.goal,
            error=error,
            last_action=str(last_action) if last_action else "无",
            history_length=len(context.history),
            max_steps=context.max_steps,
        )

        # Call LLM
        messages = [{"role": "user", "content": prompt}]
        response = await self._call_llm(messages, json_response=True)

        # Parse response
        try:
            data = self.parse_json_response(response.content)
            return Action.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to parse recovery response: {e}")
            from app.domain.agent.entities import ActionType
            return Action(
                action_type=ActionType.FAIL,
                target=None,
                parameters={},
                reasoning=f"错误恢复失败: {error}",
            )

    def _format_history(self, history: list["Step"]) -> str:
        """Format execution history for the prompt."""
        if not history:
            return "无历史记录（这是第一步）"

        # Only show last 5 steps to avoid token limit
        recent_history = history[-5:]
        lines = []

        for i, step in enumerate(recent_history, 1):
            action_str = f"{step.action.action_type.value}"
            if step.action.target:
                action_str += f"({step.action.target})"
            if step.action.parameters:
                params = ", ".join(f"{k}={v}" for k, v in step.action.parameters.items())
                action_str += f" [{params}]"

            result_str = "成功" if step.result.success else f"失败: {step.result.error or '未知错误'}"

            lines.append(f"步骤 {i}: {action_str} -> {result_str}")
            lines.append(f"  理由: {step.action.reasoning}")

        return "\n".join(lines)

    def _format_observation(self, observation: "Observation") -> str:
        """Format observation for the prompt."""
        lines = [
            f"屏幕类型: {observation.screen_type}",
            f"应用状态: {observation.app_state.to_string() if observation.app_state else '未知'}",
        ]

        if observation.visible_elements:
            elements_str = ", ".join(
                f"{e.element_type}:{e.text}" if e.text else e.element_type
                for e in observation.visible_elements[:10]  # Limit to 10 elements
            )
            lines.append(f"可见元素: {elements_str}")

        if observation.suggested_actions:
            lines.append(f"建议动作: {', '.join(observation.suggested_actions[:5])}")

        lines.append(f"描述: {observation.raw_description[:200]}...")

        return "\n".join(lines)
