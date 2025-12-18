"""Supervisor runtime configuration settings."""

from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_default_team_instructions() -> str:
    """从 Markdown 文件加载默认的团队指令."""
    prompt_path = Path(__file__).parent / "prompts" / "team_instructions.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return (
        "协作规则：\n"
        "- 团队成员主动协作，明确分工、共享实时进展。\n"
        "- 回答保持准确精炼，必要时给出引用或后续建议。\n"
        "- 若存在不确定性，说明原因并提出下一步行动。\n"
    )


class QueryAnalysisSettings(BaseSettings):
    """LLM settings for query analysis."""

    model_config = SettingsConfigDict(
        env_prefix="SUPERVISOR_RUNTIME__COORDINATION__QUERY_ANALYSIS__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    model_name: str = Field(default="anthropic:claude-3-sonnet-20240229")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100)
    timeout: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, ge=0.1)
    system_prompt: str = Field(
        default="You are an expert AI coordination system. Always respond with valid JSON only."
    )
    prompt_template: str = Field(default="unified_coordination")
    validate_response: bool = True
    require_all_fields: bool = True
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class WorkflowPlanningSettings(BaseSettings):
    """Workflow planning configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SUPERVISOR_RUNTIME__COORDINATION__WORKFLOW_PLANNING__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    max_parallel_agents: int = Field(default=10, ge=1)
    max_sequential_depth: int = Field(default=5, ge=1)
    max_hierarchical_levels: int = Field(default=3, ge=1)
    default_timeout: int = Field(default=300, ge=1)
    enable_optimization: bool = True
    prefer_parallel: bool = True
    balance_load: bool = True
    max_dependency_depth: int = Field(default=10, ge=1)
    detect_cycles: bool = True
    resolve_conflicts: bool = True


class ExecutionSettings(BaseSettings):
    """Execution engine configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SUPERVISOR_RUNTIME__COORDINATION__EXECUTION__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    default_timeout: int = Field(default=300, ge=1)
    agent_timeout: int = Field(default=60, ge=1)
    max_concurrent_executions: int = Field(default=20, ge=1)
    max_retries: int = Field(default=2, ge=0)
    retry_delay: float = Field(default=2.0, ge=0.1)
    exponential_backoff: bool = True
    enable_progress_monitoring: bool = True
    log_execution_details: bool = True
    collect_metrics: bool = True
    memory_limit_mb: int = Field(default=1024, ge=128)
    cpu_limit_percent: float = Field(default=80.0, ge=0.0, le=100.0)


class ResultConsolidationSettings(BaseSettings):
    """LLM settings for result consolidation."""

    model_config = SettingsConfigDict(
        env_prefix="SUPERVISOR_RUNTIME__COORDINATION__RESULT_CONSOLIDATION__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    model_name: str = Field(default="anthropic:claude-3-sonnet-20240229")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=3000, ge=100)
    timeout: int = Field(default=45, ge=1)
    default_strategy: str = Field(default="synthesis")
    enable_conflict_detection: bool = True
    enable_consensus_building: bool = True
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    consensus_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_conflicts: int = Field(default=5, ge=0)
    max_response_length: int = Field(default=2000, ge=100)
    include_sources: bool = True
    include_confidence: bool = True


class CoordinationSettings(BaseSettings):
    """High-level coordination configuration surface."""

    model_config = SettingsConfigDict(
        env_prefix="SUPERVISOR_RUNTIME__COORDINATION__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    max_concurrent_agents: int = Field(default=5, ge=1)
    default_timeout: int = Field(default=60, ge=5)
    enable_consensus: bool = False
    consensus_threshold: float = Field(default=0.7, ge=0.5, le=1.0)

    query_analysis: QueryAnalysisSettings = Field(default_factory=QueryAnalysisSettings)
    workflow_planning: WorkflowPlanningSettings = Field(default_factory=WorkflowPlanningSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    result_consolidation: ResultConsolidationSettings = Field(default_factory=ResultConsolidationSettings)

    enable_caching: bool = True
    cache_ttl: int = Field(default=3600, ge=1)
    enable_metrics: bool = True
    log_level: str = Field(default="INFO")
    max_concurrent_requests: int = Field(default=50, ge=1)
    request_timeout: int = Field(default=600, ge=1)
    enable_rate_limiting: bool = True


class SupervisorRuntimeSettings(BaseSettings):
    """Supervisor runtime configuration entry point."""

    model_config = SettingsConfigDict(
        env_prefix="SUPERVISOR_RUNTIME__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    coordination: CoordinationSettings = Field(default_factory=CoordinationSettings)
    enable_streaming: bool = True
    team_instructions: str = Field(
        default_factory=_load_default_team_instructions,
        description="Agno Team 级别的协作/行为指令（可通过 SUPERVISOR_RUNTIME__TEAM_INSTRUCTIONS 覆盖）",
    )
