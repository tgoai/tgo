"""Vision model client for screen analysis.

The vision model is a VLM (Vision Language Model) that:
- Analyzes screenshots and returns structured observations
- Locates UI elements based on natural language descriptions
- Verifies action results by comparing before/after screenshots
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from app.core.llm.base import BaseLLMClient

if TYPE_CHECKING:
    from app.domain.agent.entities import Observation, Position

logger = logging.getLogger(__name__)


class VisionClient(BaseLLMClient):
    """Vision model client for screen analysis.

    This client uses a VLM (e.g., qwen-vl-plus, gpt-4o) to:
    1. Analyze screen state and return structured observation
    2. Locate specific UI elements
    3. Verify action results
    """

    async def analyze_screen(
        self,
        screenshot: bytes,
        focus: Optional[str] = None,
        goal: Optional[str] = None,
    ) -> "Observation":
        """Analyze a screenshot and return structured observation.

        Args:
            screenshot: Screenshot image bytes (PNG/JPEG)
            focus: Optional focus hint for the analysis
            goal: Optional task goal for context

        Returns:
            Observation with screen type, app state, visible elements, etc.
        """
        from app.domain.agent.entities import Observation
        from app.domain.agent.prompts.vision import SCREEN_ANALYSIS_PROMPT

        # Build prompt
        prompt = SCREEN_ANALYSIS_PROMPT.format(
            focus=focus or "全局状态分析",
            goal=goal or "未指定",
        )

        # Build message with image
        messages = self._build_image_message(screenshot, prompt)

        # Call LLM
        response = await self._call_llm(messages, json_response=True)

        # Parse response
        try:
            data = self.parse_json_response(response.content)
            return Observation.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to parse observation: {e}, content: {response.content[:200]}")
            # Return a basic observation on parse error
            return Observation(
                screen_type="unknown",
                app_state=None,
                visible_elements=[],
                suggested_actions=[],
                raw_description=f"分析失败: {e}",
            )

    async def locate_element(
        self,
        screenshot: bytes,
        element_description: str,
    ) -> "Position":
        """Locate a UI element in the screenshot.

        Args:
            screenshot: Screenshot image bytes
            element_description: Natural language description of the element

        Returns:
            Position with coordinates, or Position with found=False
        """
        from app.domain.agent.entities import Position
        from app.domain.agent.prompts.vision import ELEMENT_LOCATION_PROMPT

        # Build prompt
        prompt = ELEMENT_LOCATION_PROMPT.format(element=element_description)

        # Build message with image
        messages = self._build_image_message(screenshot, prompt)

        # Call LLM
        response = await self._call_llm(messages, json_response=True)

        # Parse response
        try:
            data = self.parse_json_response(response.content)

            # Log detailed location result for debugging
            logger.info(
                f"Element location result: target='{element_description}', "
                f"found={data.get('found')}, position={data.get('position')}, "
                f"confidence={data.get('confidence')}, enabled={data.get('enabled', True)}, "
                f"description='{data.get('description', '')[:100]}'"
            )

            if not data.get("found", False):
                logger.warning(f"Element not found: {element_description}")
                return Position(
                    x=0,
                    y=0,
                    width=None,
                    height=None,
                    found=False,
                    confidence=0.0,
                    description=data.get("description", "元素未找到"),
                    enabled=False,
                )

            pos = data.get("position", {})
            is_enabled = data.get("enabled", True)

            position = Position(
                x=pos.get("x", 0),
                y=pos.get("y", 0),
                width=pos.get("width"),
                height=pos.get("height"),
                found=True,
                confidence=data.get("confidence", 0.0),
                description=data.get("description", ""),
                enabled=is_enabled,
            )

            # Log position details (x, y are now center coordinates)
            logger.debug(
                f"Element '{element_description}' position: ({position.x}, {position.y}), "
                f"size: {position.width}x{position.height}, "
                f"enabled: {position.enabled}, confidence: {position.confidence}"
            )

            # Warn if element is disabled
            if not is_enabled:
                logger.warning(f"Element '{element_description}' is DISABLED (not clickable)")

            return position

        except Exception as e:
            logger.error(f"Failed to parse position: {e}")
            return Position(
                x=0,
                y=0,
                found=False,
                confidence=0.0,
                description=f"解析失败: {e}",
            )

    async def verify_action(
        self,
        before: bytes,
        after: bytes,
        expected_change: str,
    ) -> tuple[bool, str]:
        """Verify if an action produced the expected result.

        Args:
            before: Screenshot before the action
            after: Screenshot after the action
            expected_change: Description of expected change

        Returns:
            Tuple of (success, explanation)
        """
        from app.domain.agent.prompts.vision import ACTION_VERIFICATION_PROMPT

        # Build prompt
        prompt = ACTION_VERIFICATION_PROMPT.format(expected_change=expected_change)

        # Build message with both images
        messages = self._build_comparison_message(before, after, prompt)

        # Call LLM
        response = await self._call_llm(messages, json_response=True)

        # Parse response
        try:
            data = self.parse_json_response(response.content)
            success = data.get("success", False)
            explanation = data.get("explanation", "无解释")
            return success, explanation
        except Exception as e:
            logger.error(f"Failed to parse verification: {e}")
            return False, f"验证解析失败: {e}"

    def _build_image_message(
        self,
        image: bytes,
        prompt: str,
    ) -> list[dict[str, Any]]:
        """Build message with image for API call."""
        image_base64, image_type = self._prepare_image_data(image)

        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_type};base64,{image_base64}"
                        },
                    },
                ],
            }
        ]

    def _build_comparison_message(
        self,
        before: bytes,
        after: bytes,
        prompt: str,
    ) -> list[dict[str, Any]]:
        """Build message with two images for comparison."""
        before_base64, before_type = self._prepare_image_data(before)
        after_base64, after_type = self._prepare_image_data(after)

        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{before_type};base64,{before_base64}"
                        },
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{after_type};base64,{after_base64}"
                        },
                    },
                ],
            }
        ]
