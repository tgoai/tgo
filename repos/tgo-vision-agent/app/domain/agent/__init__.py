"""Agent module for ReAct-style UI automation.

This module provides:
- AgentLoop: Core execution engine with Observe -> Think -> Act loop
- Entities: Observation, Action, Step, AgentContext, etc.
- Prompts: Reasoning and vision model prompt templates
"""

from app.domain.agent.entities import (
    Action,
    ActionType,
    AgentContext,
    AgentResult,
    Observation,
    Position,
    Step,
    StepResult,
    UIElement,
    AppState,
)
from app.domain.agent.agent_loop import AgentLoop

__all__ = [
    "Action",
    "ActionType",
    "AgentContext",
    "AgentLoop",
    "AgentResult",
    "Observation",
    "Position",
    "Step",
    "StepResult",
    "UIElement",
    "AppState",
]
