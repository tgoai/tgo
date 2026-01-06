"""AI service client for proxying requests to external AI service."""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from uuid import uuid4, UUID

from datetime import date, datetime

import httpx
from fastapi import HTTPException


from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ai_client")


class AIServiceClient:
    """Client for communicating with the external AI service."""

    def __init__(self):
        self.base_url = str(settings.AI_SERVICE_URL).rstrip("/")
        self.timeout = settings.AI_SERVICE_TIMEOUT
        self.api_key = settings.AI_SERVICE_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for AI service requests (no auth required by downstream)."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TGO-API-Service/0.1.0",
        }
        # Authentication headers have been removed per latest AI service API spec
        return headers
    def _to_jsonable(self, obj: Any) -> Any:
        """Recursively convert data to JSON-serializable primitives (str/int/bool/list/dict).
        Handles UUID, datetime/date, sets, and Pydantic models (via model_dump if present).
        """
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {str(k): self._to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [self._to_jsonable(v) for v in obj]
        # Support Pydantic models without importing pydantic explicitly
        if hasattr(obj, "model_dump"):
            try:
                return self._to_jsonable(obj.model_dump(exclude_none=True))
            except Exception:
                pass
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return str(obj)


    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make HTTP request to AI service."""
        url = f"{self.base_url}{endpoint}"
        request_id = str(uuid4())

        headers = self._get_headers()
        headers["X-Request-ID"] = request_id

        logger.info(
            f"AI service request: {method} {url}",
            extra={
                "request_id": request_id,
                "method": method,
                "url": url,
                "params": params,
            }
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=self._to_jsonable(json_data),
                    params=params,
                )

                logger.info(
                    f"AI service response: {response.status_code}",
                    extra={
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds() if response.elapsed else None,
                    }
                )

                return response

        except httpx.TimeoutException as e:
            logger.error(
                f"AI service timeout: {url}",
                extra={"request_id": request_id, "timeout": self.timeout}
            )
            raise HTTPException(
                status_code=504,
                detail="AI service request timed out"
            )
        except httpx.RequestError as e:
            logger.error(
                f"AI service request error: {e}",
                extra={"request_id": request_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to connect to AI service"
            )

    async def _handle_response(self, response: httpx.Response) -> Any:
        """Handle AI service response and convert errors."""
        if response.is_success:
            if response.status_code == 204:
                return None
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text

        # Handle error responses
        try:
            error_data = response.json()
        except json.JSONDecodeError:
            error_data = {"error": {"message": response.text or "Unknown error"}}

        logger.warning(
            f"AI service error response: {response.status_code}",
            extra={
                "status_code": response.status_code,
                "error_data": error_data,
            }
        )

        raise HTTPException(
            status_code=response.status_code,
            detail=error_data
        )

    # Team endpoints
    async def list_teams(
        self,
        project_id: str,
        is_default: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List teams from AI service."""
        params = {"limit": limit, "offset": offset, "project_id": project_id}
        if is_default is not None:
            params["is_default"] = is_default

        response = await self._make_request(
            "GET", "/api/v1/teams", params=params
        )
        return await self._handle_response(response)

    async def create_team(
        self,
        project_id: str,
        team_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create team in AI service."""
        response = await self._make_request(
            "POST", "/api/v1/teams", json_data=team_data, params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def get_team(
        self,
        project_id: str,
        team_id: str,
        include_agents: bool = True,
    ) -> Dict[str, Any]:
        """Get team from AI service."""
        params = {"include_agents": include_agents, "project_id": project_id}
        response = await self._make_request(
            "GET", f"/api/v1/teams/{team_id}", params=params
        )
        return await self._handle_response(response)

    async def update_team(
        self,
        project_id: str,
        team_id: str,
        team_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update team in AI service."""
        response = await self._make_request(
            "PATCH", f"/api/v1/teams/{team_id}", json_data=team_data, params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def delete_team(
        self,
        project_id: str,
        team_id: str,
    ) -> None:
        """Delete team from AI service."""
        response = await self._make_request(
            "DELETE", f"/api/v1/teams/{team_id}", params={"project_id": project_id}
        )
        return await self._handle_response(response)

    # Agent endpoints
    async def run_supervisor_agent(
        self,
        message: str,
        project_id: str,
        *,
        team_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        stream: bool = False,
        config: Optional[Dict[str, Any]] = None,
        mcp_url: Optional[str] = None,
        rag_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run supervisor agent workflow and return response content."""
        payload: Dict[str, Any] = {
            "message": message,
            "stream": stream,
        }
        if team_id:
            payload["team_id"] = team_id
        if session_id:
            payload["session_id"] = session_id
        if user_id:
            payload["user_id"] = user_id
        if config:
            payload["config"] = config
        if mcp_url:
            payload["mcp_url"] = mcp_url
        if rag_url:
            payload["rag_url"] = rag_url

        response = await self._make_request(
            "POST",
            "/api/v1/agents/run",
            json_data=payload,
            params={"project_id": project_id},
        )
        data = await self._handle_response(response)
        if isinstance(data, dict):
            return data

        return {"content": data}

    async def run_supervisor_agent_stream(
        self,
        message: str,
        project_id: str,
        *,
        team_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        mcp_url: Optional[str] = None,
        rag_url: Optional[str] = None,
        enable_memory: Optional[bool] = None,
        system_message: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_ids: Optional[List[str]] = None,
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """Stream supervisor agent events as they arrive."""
        payload: Dict[str, Any] = {
            "message": message,
            "stream": True,
        }
        if team_id:
            payload["team_id"] = team_id
        if agent_id:
            payload["agent_id"] = agent_id
        if agent_ids:
            payload["agent_ids"] = agent_ids
        if session_id:
            payload["session_id"] = session_id
        if user_id:
            payload["user_id"] = user_id
        if config:
            payload["config"] = config
        if mcp_url:
            payload["mcp_url"] = mcp_url
        if rag_url:
            payload["rag_url"] = rag_url
        if enable_memory is not None:
            payload["enable_memory"] = enable_memory
        if system_message is not None:
            payload["system_message"] = system_message
        if expected_output is not None:
            payload["expected_output"] = expected_output

        url = f"{self.base_url}/api/v1/agents/run"
        request_id = str(uuid4())
        headers = self._get_headers()
        headers["X-Request-ID"] = request_id
        headers.setdefault("Accept", "text/event-stream")

        logger.info(
            "AI service stream request: POST %s",
            url,
            extra={"request_id": request_id},
        )

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=headers,
                    json=self._to_jsonable(payload),
                    params={"project_id": project_id},
                ) as response:
                    if response.status_code != 200:
                        try:
                            error_data = await response.json()
                        except Exception:
                            error_body = await response.aread()
                            error_data = {"error": error_body.decode("utf-8", errors="ignore")}
                        logger.warning(
                            "AI service stream error: %s",
                            response.status_code,
                            extra={"request_id": request_id, "detail": error_data},
                        )
                        raise HTTPException(status_code=response.status_code, detail=error_data)

                    event_name: Optional[str] = None
                    data_lines: List[str] = []

                    async for line in response.aiter_lines():
                        if not line:
                            if not data_lines:
                                event_name = None
                                continue
                            data_text = '\n'.join(data_lines)
                            try:
                                parsed = json.loads(data_text)
                            except json.JSONDecodeError:
                                parsed = data_text
                            yield (event_name or "message", parsed)
                            event_name = None
                            data_lines = []
                            continue
                        if line.startswith(":"):
                            continue
                        if line.startswith("event:"):
                            event_name = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line.split(":", 1)[1].strip())

                    if data_lines:
                        data_text = '\n'.join(data_lines)
                        try:
                            parsed = json.loads(data_text)
                        except json.JSONDecodeError:
                            parsed = data_text
                        yield (event_name or "message", parsed)
        except httpx.TimeoutException:
            logger.error("AI service stream timeout: %s", url, extra={"request_id": request_id})
            raise HTTPException(status_code=504, detail="AI service stream timed out")
        except httpx.RequestError as exc:
            logger.error("AI service stream request error: %s", exc, extra={"request_id": request_id})
            raise HTTPException(status_code=502, detail="Failed to connect to AI service")

    async def cancel_supervisor_run(
        self,
        project_id: str,
        run_id: str,
        reason: Optional[str] = None,
    ) -> Any:
        """Cancel a running supervisor team execution by run_id.
        Proxies to AI service: POST /api/v1/agents/run/{run_id}/cancel
        """
        body = {"reason": reason} if reason else None
        response = await self._make_request(
            "POST",
            f"/api/v1/agents/run/{run_id}/cancel",
            json_data=body,
            params={"project_id": project_id},
        )
        return await self._handle_response(response)



    async def check_agents_exist(
        self,
        project_id: str,
    ) -> bool:
        """
        Check if any agents exist for the specified project.
        
        Args:
            project_id: Project ID to check
            
        Returns:
            True if agents exist, False otherwise
        """
        try:
            response = await self._make_request(
                "GET",
                "/api/v1/agents/exists",
                params={"project_id": project_id},
            )
            data = await self._handle_response(response)
            if isinstance(data, dict):
                return data.get("exists", False)
            return False
        except HTTPException:
            # If the check fails, assume agents exist to avoid blocking
            logger.warning(
                f"Failed to check agents existence for project {project_id}, assuming agents exist"
            )
            return True
        except Exception as e:
            logger.warning(
                f"Unexpected error checking agents existence: {e}, assuming agents exist"
            )
            return True

    async def list_agents(
        self,
        project_id: str,
        team_id: Optional[str] = None,
        model: Optional[str] = None,
        is_default: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List agents from AI service."""
        params = {"limit": limit, "offset": offset, "project_id": project_id}
        if team_id:
            params["team_id"] = team_id
        if model:
            params["model"] = model
        if is_default is not None:
            params["is_default"] = is_default

        response = await self._make_request(
            "GET", "/api/v1/agents", params=params
        )
        return await self._handle_response(response)

    async def create_agent(
        self,
        project_id: str,
        agent_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create agent in AI service."""
        response = await self._make_request(
            "POST", "/api/v1/agents", json_data=agent_data, params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def get_agent(
        self,
        project_id: str,
        agent_id: str,
        include_tools: bool = True,
        include_collections: bool = False,
        include_workflows: bool = False,
    ) -> Dict[str, Any]:
        """Get agent from AI service."""
        params = {
            "include_tools": include_tools,
            "include_collections": include_collections,
            "include_workflows": include_workflows,
            "project_id": project_id,
        }
        response = await self._make_request(
            "GET", f"/api/v1/agents/{agent_id}", params=params
        )
        return await self._handle_response(response)

    async def update_agent(
        self,
        project_id: str,
        agent_id: str,
        agent_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update agent in AI service."""
        response = await self._make_request(
            "PATCH", f"/api/v1/agents/{agent_id}", json_data=agent_data, params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def delete_agent(
        self,
        project_id: str,
        agent_id: str,
    ) -> None:
        """Delete agent from AI service."""
        response = await self._make_request(
            "DELETE", f"/api/v1/agents/{agent_id}", params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def set_agent_tool_enabled(
        self,
        project_id: str,
        agent_id: str,
        tool_id: str,
        enabled: bool,
    ) -> None:
        """Enable or disable a specific tool binding for an agent."""
        response = await self._make_request(
            "PATCH",
            f"/api/v1/agents/{agent_id}/tools/{tool_id}/enabled",
            json_data={"enabled": enabled},
            params={"project_id": project_id}
        )
        # 204 No Content response
        if response.status_code == 204:
            return None
        return await self._handle_response(response)

    async def set_agent_collection_enabled(
        self,
        project_id: str,
        agent_id: str,
        collection_id: str,
        enabled: bool,
    ) -> None:
        """Enable or disable a specific collection binding for an agent."""
        response = await self._make_request(
            "PATCH",
            f"/api/v1/agents/{agent_id}/collections/{collection_id}/enabled",
            json_data={"enabled": enabled},
            params={"project_id": project_id}
        )
        # 204 No Content response
        if response.status_code == 204:
            return None
        return await self._handle_response(response)

    async def set_agent_workflow_enabled(
        self,
        project_id: str,
        agent_id: str,
        workflow_id: str,
        enabled: bool,
    ) -> None:
        """Enable or disable a specific workflow binding for an agent."""
        response = await self._make_request(
            "PATCH",
            f"/api/v1/agents/{agent_id}/workflows/{workflow_id}/enabled",
            json_data={"enabled": enabled},
            params={"project_id": project_id}
        )
        # 204 No Content response
        if response.status_code == 204:
            return None
        return await self._handle_response(response)


    # Tools endpoints
    async def list_tools(
        self,
        project_id: str,
        tool_type: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        """List tools from AI service."""
        params = {"project_id": project_id, "include_deleted": include_deleted}
        if tool_type:
            params["tool_type"] = tool_type

        response = await self._make_request(
            "GET", "/api/v1/tools", params=params
        )
        return await self._handle_response(response)

    async def create_tool(
        self,
        tool_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create tool in AI service."""
        response = await self._make_request(
            "POST", "/api/v1/tools", json_data=tool_data
        )
        return await self._handle_response(response)

    async def update_tool(
        self,
        project_id: str,
        tool_id: str,
        tool_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update tool in AI service."""
        response = await self._make_request(
            "PATCH",
            f"/api/v1/tools/{tool_id}",
            json_data=tool_data,
            params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def delete_tool(
        self,
        project_id: str,
        tool_id: str,
    ) -> Dict[str, Any]:
        """Delete tool from AI service (soft delete)."""
        response = await self._make_request(
            "DELETE", f"/api/v1/tools/{tool_id}", params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def create_or_update_tool(
        self,
        project_id: str,
        tool_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create or update a tool in the AI service."""
        tool_name = tool_data.get("name")
        # Check if tool already exists
        existing_tools = await self.list_tools(project_id)
        existing_tool = next((t for t in existing_tools if t["name"] == tool_name), None)

        if existing_tool:
            # Update existing tool
            return await self.update_tool(project_id, existing_tool["id"], tool_data)
        else:
            # Create new tool
            # create_tool in AI service expects tool_data with project_id
            data = {**tool_data, "project_id": project_id}
            return await self.create_tool(data)

    async def delete_tools_by_prefix(
        self,
        project_id: str,
        prefix: str,
    ) -> None:
        """Delete all tools with names starting with prefix."""
        tools = await self.list_tools(project_id)
        for tool in tools:
            if tool["name"].startswith(prefix):
                await self.delete_tool(project_id, tool["id"])












    # Chat completions endpoint
    async def chat_completions(
        self,
        project_id: str,
        provider_id: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a chat completion using the AI service.
        
        This proxies to the AI service's /api/v1/chat/completions endpoint,
        which is compatible with OpenAI's Chat Completions API format.
        
        Args:
            project_id: Project ID for authorization
            provider_id: UUID of the LLM provider to use
            model: Model identifier (e.g., 'gpt-4', 'claude-3-opus')
            messages: List of conversation messages with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response (not supported yet)
            
        Returns:
            Chat completion response with choices
        """
        payload: Dict[str, Any] = {
            "provider_id": provider_id,
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        response = await self._make_request(
            "POST",
            "/api/v1/chat/completions",
            json_data=payload,
            params={"project_id": project_id},
        )
        return await self._handle_response(response)


# Global AI client instance
ai_client = AIServiceClient()
