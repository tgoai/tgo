"""AgentLoop - Core execution engine for ReAct-style UI automation.

The AgentLoop implements a Observe -> Think -> Act loop:
1. Observe: Vision model analyzes the current screen
2. Think: Reasoning model decides the next action
3. Act: Execute the action via AgentBay controller
4. Repeat until complete or max steps reached
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple

from app.domain.agent.entities import (
    Action,
    ActionType,
    AgentContext,
    AgentResult,
    Observation,
    Position,
    Step,
    StepResult,
)

if TYPE_CHECKING:
    from app.core.llm.reasoning import ReasoningClient
    from app.core.llm.vision import VisionClient
    from app.domain.ports import AgentBayController

logger = logging.getLogger(__name__)

# Constants for loop detection
LOOP_DETECTION_WINDOW = 3  # Number of recent steps to check for loops
LOOP_SIMILARITY_THRESHOLD = 3  # Consecutive similar actions to trigger loop detection
MAX_LOOP_TOLERANCE = 5  # Maximum consecutive loop detections before forced failure

# Constants for confidence handling
LOW_CONFIDENCE_THRESHOLD = 0.7  # Below this, warn about potential inaccuracy


class AgentLoop:
    """Agent main loop implementing ReAct pattern.

    This class coordinates:
    - VisionClient for screen analysis (Observe)
    - ReasoningClient for decision making (Think)
    - AgentBayController for action execution (Act)
    """

    def __init__(
        self,
        reasoning: "ReasoningClient",
        vision: "VisionClient",
        controller: "AgentBayController",
        session_id: str,
    ):
        """Initialize the agent loop.

        Args:
            reasoning: Reasoning model client for decision making
            vision: Vision model client for screen analysis
            controller: AgentBay controller for executing actions
            session_id: AgentBay session ID
        """
        self.reasoning = reasoning
        self.vision = vision
        self.controller = controller
        self.session_id = session_id
        self._consecutive_loop_count = 0  # Track consecutive loop detections

    def _detect_loop(self, history: list[Step]) -> Tuple[bool, Optional[str]]:
        """Detect if the agent is stuck in a loop.

        Checks if recent actions are repetitive (same action_type and similar target).

        Args:
            history: List of executed steps

        Returns:
            Tuple of (is_loop_detected, loop_description)
        """
        if len(history) < LOOP_DETECTION_WINDOW:
            return False, None

        # Get recent actions
        recent_steps = history[-LOOP_DETECTION_WINDOW:]
        recent_actions = [step.action for step in recent_steps]

        # Check for consecutive identical actions
        first_action = recent_actions[0]
        all_same_type = all(
            a.action_type == first_action.action_type for a in recent_actions
        )

        if not all_same_type:
            return False, None

        # Check if targets are similar (same or very similar)
        targets = [a.target or "" for a in recent_actions]
        first_target = targets[0].lower()

        # Count how many targets are similar to the first one
        similar_count = sum(
            1 for t in targets if t.lower() == first_target or
            (first_target and first_target in t.lower()) or
            (t.lower() and t.lower() in first_target)
        )

        if similar_count >= LOOP_SIMILARITY_THRESHOLD:
            loop_desc = (
                f"检测到循环！最近 {LOOP_DETECTION_WINDOW} 次操作都是 "
                f"{first_action.action_type.value}({first_target or '无目标'})。"
                f"请尝试不同的策略，不要再执行相同的动作。"
            )
            logger.warning(f"Loop detected: {loop_desc}")
            return True, loop_desc

        return False, None

    async def run(self, context: AgentContext) -> AgentResult:
        """Execute the agent loop until completion or failure.

        Args:
            context: Agent execution context with goal, app info, etc.

        Returns:
            AgentResult with success status and execution details
        """
        logger.info(f"Starting agent loop for goal: {context.goal}")

        for step_num in range(context.max_steps):
            try:
                # 1. Observe - Take screenshot and analyze with vision model
                screenshot = await self.controller.take_screenshot(self.session_id)
                observation = await self.vision.analyze_screen(
                    screenshot,
                    focus=context.goal,
                    goal=context.goal,
                )

                logger.info(f"Step {step_num + 1} Observation: screen_type={observation.screen_type}, app_state={observation.app_state.to_string() if observation.app_state else 'unknown'}")
                logger.debug(f"Observation details: {observation.raw_description}")

                # 1.5 Check for loops
                is_loop, loop_hint = self._detect_loop(context.history)

                if is_loop:
                    self._consecutive_loop_count += 1
                    logger.warning(f"Loop detected, consecutive count: {self._consecutive_loop_count}")

                    # Force failure if loop persists too long
                    if self._consecutive_loop_count >= MAX_LOOP_TOLERANCE:
                        logger.error(f"Max loop tolerance ({MAX_LOOP_TOLERANCE}) exceeded, forcing failure")
                        return AgentResult(
                            success=False,
                            message=f"Agent 陷入循环无法恢复，已连续 {self._consecutive_loop_count} 次检测到相同操作",
                            steps_taken=step_num + 1,
                            history=context.history,
                        )
                else:
                    # Reset loop counter when no loop detected
                    self._consecutive_loop_count = 0

                # 2. Think - Reasoning model decides next action
                action = await self.reasoning.decide_action(
                    observation=observation,
                    goal=context.goal,
                    history=context.history,
                    available_apps=context.installed_apps,
                    loop_hint=loop_hint,  # Pass loop hint to reasoning model
                )

                logger.info(f"Step {step_num + 1}: Action={action}")

                # 3. Check for completion
                if action.action_type == ActionType.COMPLETE:
                    logger.info(f"Task completed: {action.reasoning}")
                    return AgentResult(
                        success=True,
                        message=action.reasoning,
                        steps_taken=step_num + 1,
                        history=context.history,
                    )

                if action.action_type == ActionType.FAIL:
                    logger.warning(f"Task failed: {action.reasoning}")
                    return AgentResult(
                        success=False,
                        message=action.reasoning,
                        steps_taken=step_num + 1,
                        history=context.history,
                    )

                # 4. Act - Execute the action
                result = await self._execute_action(action, screenshot)

                # 5. Record history
                step = Step(
                    observation=observation,
                    action=action,
                    result=result,
                    timestamp=datetime.now(),
                )
                context.history.append(step)

                # 6. Handle failure with recovery
                if not result.success:
                    logger.warning(f"Action failed: {result.error}")
                    # Let reasoning model decide recovery in next iteration
                    # The failure will be visible in history

                # 7. Wait for UI to settle
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error in agent loop step {step_num + 1}: {e}", exc_info=True)
                # Record the error and continue
                error_step = Step(
                    observation=Observation(
                        screen_type="error",
                        raw_description=str(e),
                    ),
                    action=Action(
                        action_type=ActionType.FAIL,
                        reasoning=f"执行错误: {e}",
                    ),
                    result=StepResult(success=False, error=str(e)),
                    timestamp=datetime.now(),
                )
                context.history.append(error_step)

        # Max steps reached
        logger.warning(f"Max steps ({context.max_steps}) reached")
        return AgentResult(
            success=False,
            message=f"达到最大步数限制 ({context.max_steps})",
            steps_taken=context.max_steps,
            history=context.history,
        )

    async def _execute_action(
        self,
        action: Action,
        screenshot: bytes,
    ) -> StepResult:
        """Execute a single action.

        Args:
            action: The action to execute
            screenshot: Current screenshot (for element location if needed)

        Returns:
            StepResult with success status
        """
        logger.info(f"Executing action: {action.action_type.value}, target: {action.target}, params: {action.parameters}")
        try:
            success = False

            match action.action_type:
                case ActionType.CLICK:
                    success = await self._execute_click(action, screenshot)

                case ActionType.TYPE:
                    text = action.parameters.get("text", "")
                    if not text:
                        return StepResult(success=False, error="缺少输入文本")
                    success = await self.controller.type_text(self.session_id, text)

                case ActionType.LAUNCH_APP:
                    package = action.parameters.get("package") or action.target
                    if not package:
                        return StepResult(success=False, error="缺少应用包名")
                    success = await self.controller.launch_app(self.session_id, package)

                case ActionType.PRESS_BACK:
                    success = await self.controller.press_back(self.session_id)

                case ActionType.SCROLL:
                    success = await self._execute_scroll(action)

                case ActionType.SWIPE:
                    success = await self._execute_swipe(action)

                case ActionType.WAIT:
                    duration = action.parameters.get("duration", 2)
                    await asyncio.sleep(duration)
                    success = True

                case _:
                    return StepResult(
                        success=False,
                        error=f"未知动作类型: {action.action_type}",
                    )

            logger.info(f"Action executed: {action.action_type.value}, success: {success}")
            return StepResult(success=success)

        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return StepResult(success=False, error=str(e))

    async def _execute_click(self, action: Action, screenshot: bytes) -> bool:
        """Execute a click action.

        If action has explicit coordinates in parameters, use them.
        Otherwise, use vision model to locate the target element.
        """
        # Check for explicit coordinates
        if "x" in action.parameters and "y" in action.parameters:
            x = action.parameters["x"]
            y = action.parameters["y"]
            logger.info(f"Using explicit coordinates: ({x}, {y})")
            return await self.controller.click(self.session_id, x, y)

        # Use vision model to locate element
        if not action.target:
            logger.error("Click action missing target and coordinates")
            return False

        position = await self.vision.locate_element(screenshot, action.target)

        if not position.found:
            logger.warning(f"Element not found: {action.target}")
            return False

        # Check confidence level
        if position.confidence < LOW_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"Low confidence ({position.confidence:.2f}) for element '{action.target}'. "
                f"Position may be inaccurate. Consider scrolling to make element more visible."
            )

        # Check if element is enabled
        if not position.enabled:
            logger.warning(
                f"Element '{action.target}' is DISABLED (enabled=False). "
                f"Click may not work. Consider scrolling first to activate the button."
            )
            # Still attempt the click, but log this for debugging

        # Click at center of element (x, y are already center coordinates)
        x = position.center_x
        y = position.center_y

        logger.info(f"Clicking at ({x}, {y}) for target: '{action.target}' "
                    f"(confidence: {position.confidence:.2f}, enabled: {position.enabled})")
        return await self.controller.click(self.session_id, x, y)

    async def _execute_scroll(self, action: Action) -> bool:
        """Execute a scroll action."""
        direction = action.parameters.get("direction", "down")
        amount = action.parameters.get("amount", 300)

        # Get screen dimensions (assume standard mobile)
        center_x = 540  # Approximate center
        center_y = 960

        if direction == "down":
            start_y = center_y + amount // 2
            end_y = center_y - amount // 2
            return await self.controller.swipe(
                self.session_id,
                center_x,
                start_y,
                center_x,
                end_y,
            )
        elif direction == "up":
            start_y = center_y - amount // 2
            end_y = center_y + amount // 2
            return await self.controller.swipe(
                self.session_id,
                center_x,
                start_y,
                center_x,
                end_y,
            )
        elif direction == "left":
            start_x = center_x + amount // 2
            end_x = center_x - amount // 2
            return await self.controller.swipe(
                self.session_id,
                start_x,
                center_y,
                end_x,
                center_y,
            )
        elif direction == "right":
            start_x = center_x - amount // 2
            end_x = center_x + amount // 2
            return await self.controller.swipe(
                self.session_id,
                start_x,
                center_y,
                end_x,
                center_y,
            )

        return False

    async def _execute_swipe(self, action: Action) -> bool:
        """Execute a swipe action with explicit coordinates."""
        start_x = action.parameters.get("start_x", 540)
        start_y = action.parameters.get("start_y", 960)
        end_x = action.parameters.get("end_x", 540)
        end_y = action.parameters.get("end_y", 660)

        return await self.controller.swipe(
            self.session_id,
            start_x,
            start_y,
            end_x,
            end_y,
        )

    async def run_single_task(
        self,
        goal: str,
        app_type: str,
        app_package: Optional[str] = None,
        max_steps: int = 20,
    ) -> AgentResult:
        """Convenience method to run a single task.

        Args:
            goal: Task goal description
            app_type: Application type (wechat, douyin, etc.)
            app_package: Optional target app package name
            max_steps: Maximum steps allowed

        Returns:
            AgentResult
        """
        # Get installed apps for context
        try:
            installed_apps = await self.controller.get_installed_apps(self.session_id)
        except Exception:
            installed_apps = []

        context = AgentContext(
            goal=goal,
            app_type=app_type,
            session_id=self.session_id,
            installed_apps=installed_apps,
            app_package=app_package,
            max_steps=max_steps,
        )

        return await self.run(context)
