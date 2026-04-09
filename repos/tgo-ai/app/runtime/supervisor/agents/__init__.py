"""
System agents for coordination system v2.

This package provides specialized system agents used internally
by the coordination system for various coordination tasks.
"""

from .system_agents import (
    create_query_analysis_agent,
    create_result_consolidation_agent,
    get_system_agent_by_type,
    create_system_agents,
    get_result_consolidation_instruction,
)
from .builder import AgnoAgentBuilder, BuiltAgent
from .runner import AgnoAgentRunner, AgentRunResult

__all__ = [
    "AgnoAgentBuilder",
    "AgnoAgentRunner",
    "AgentRunResult",
    "BuiltAgent",
    "create_query_analysis_agent",
    "create_result_consolidation_agent", 
    "get_system_agent_by_type",
    "create_system_agents",
    "get_result_consolidation_instruction",
]
