"""Pydantic schemas for plugin installation and lifecycle management."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PluginSourceGithub(BaseModel):
    """GitHub source configuration."""
    repo: str
    ref: str = "main"
    path: str = "/"


class PluginSourceBinary(BaseModel):
    """Binary source configuration."""
    url: str


class PluginSourceConfig(BaseModel):
    """Source configuration."""
    github: Optional[PluginSourceGithub] = None
    binary: Optional[PluginSourceBinary] = None


class PluginBuildGo(BaseModel):
    """Go build configuration."""
    main: str = "./cmd/plugin"
    output: str = "plugin"


class PluginBuildPython(BaseModel):
    """Python build configuration."""
    entrypoint: str = "main.py"
    requirements: str = "requirements.txt"


class PluginBuildNodeJS(BaseModel):
    """Node.js build configuration."""
    entrypoint: str = "index.js"
    package: str = "package.json"


class PluginBuildConfig(BaseModel):
    """Build configuration."""
    language: str  # go | python | nodejs
    go: Optional[PluginBuildGo] = None
    python: Optional[PluginBuildPython] = None
    nodejs: Optional[PluginBuildNodeJS] = None


class PluginRuntimeConfig(BaseModel):
    """Runtime configuration."""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    auto_restart: bool = True
    restart_delay: int = 5


class PluginInstallRequest(BaseModel):
    """Request to install a plugin."""
    id: str
    project_id: str
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    source: PluginSourceConfig
    build: Optional[PluginBuildConfig] = None
    runtime: PluginRuntimeConfig = Field(default_factory=PluginRuntimeConfig)


class PluginLifecycleResponse(BaseModel):
    """Response for plugin lifecycle actions (start/stop/restart)."""
    success: bool
    message: str
    status: Optional[str] = None
    pid: Optional[int] = None


class PluginLogResponse(BaseModel):
    """Response for plugin logs."""
    plugin_id: str
    logs: List[str]


class PluginFetchRequest(BaseModel):
    """Request to fetch plugin info from a URL."""
    url: str = Field(..., description="Plugin URL (GitHub, Gitee, or custom)")


class PluginFetchResponse(BaseModel):
    """Information fetched from a plugin's YAML configuration."""
    id: str
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    source: PluginSourceConfig
    build: Optional[PluginBuildConfig] = None
    runtime: PluginRuntimeConfig = Field(default_factory=PluginRuntimeConfig)
    source_url: str

