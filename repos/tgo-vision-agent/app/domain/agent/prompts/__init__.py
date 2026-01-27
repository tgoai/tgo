"""Prompt templates for reasoning and vision models."""

from app.domain.agent.prompts.reasoning import (
    ACTION_DECISION_PROMPT,
    ERROR_RECOVERY_PROMPT,
)
from app.domain.agent.prompts.vision import (
    SCREEN_ANALYSIS_PROMPT,
    ELEMENT_LOCATION_PROMPT,
    ACTION_VERIFICATION_PROMPT,
)

__all__ = [
    "ACTION_DECISION_PROMPT",
    "ERROR_RECOVERY_PROMPT",
    "SCREEN_ANALYSIS_PROMPT",
    "ELEMENT_LOCATION_PROMPT",
    "ACTION_VERIFICATION_PROMPT",
]
