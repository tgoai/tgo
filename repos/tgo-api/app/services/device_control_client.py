"""Device Control Service Client - HTTP client for tgo-device-control service."""

from typing import Any, AsyncGenerator, Dict, Optional
import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("services.device_control_client")


class DeviceControlClient:
    """HTTP client for communicating with tgo-device-control service."""

    def __init__(self):
        self.base_url = settings.DEVICE_CONTROL_SERVICE_URL.rstrip("/")
        self.timeout = settings.DEVICE_CONTROL_SERVICE_TIMEOUT

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request to the device control service."""
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Device control service error: {e.response.status_code} - {e.response.text}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(f"Device control service connection error: {e}")
                raise

    # Device Management

    async def list_devices(
        self,
        project_id: str,
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List devices for a project."""
        params = {
            "project_id": project_id,
            "skip": skip,
            "limit": limit,
        }
        if device_type:
            params["device_type"] = device_type
        if status:
            params["status"] = status

        return await self._request("GET", "/v1/devices", params=params)

    async def get_device(
        self,
        device_id: str,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific device."""
        params = {"project_id": project_id}
        return await self._request("GET", f"/v1/devices/{device_id}", params=params)

    async def generate_bind_code(self, project_id: str) -> Dict[str, Any]:
        """Generate a bind code for device registration."""
        params = {"project_id": project_id}
        return await self._request("POST", "/v1/devices/bind-code", params=params)

    async def update_device(
        self,
        device_id: str,
        project_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update a device."""
        params = {"project_id": project_id}
        return await self._request(
            "PATCH", f"/v1/devices/{device_id}", params=params, json=data
        )

    async def delete_device(
        self,
        device_id: str,
        project_id: str,
    ) -> bool:
        """Delete a device."""
        params = {"project_id": project_id}
        await self._request("DELETE", f"/v1/devices/{device_id}", params=params)
        return True

    async def disconnect_device(
        self,
        device_id: str,
        project_id: str,
    ) -> bool:
        """Force disconnect a device."""
        params = {"project_id": project_id}
        await self._request(
            "POST", f"/v1/devices/{device_id}/disconnect", params=params
        )
        return True

    # Agent Operations

    async def run_agent_stream(
        self,
        device_id: str,
        task: str,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        project_id: Optional[str] = None,
        max_iterations: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run the MCP Agent on a device with streaming response.
        
        Args:
            device_id: ID of the device to control.
            task: Task description to execute.
            provider_id: AI Provider ID for LLM calls via tgo-ai service.
            model: LLM model to use.
            project_id: Project ID for authorization.
            max_iterations: Optional max iterations.
            system_prompt: Optional custom system prompt.
            
        Yields:
            SSE event strings from the agent execution.
        """
        url = f"{self.base_url}/v1/agent/run"
        
        payload: Dict[str, Any] = {
            "device_id": device_id,
            "task": task,
            "stream": True,
        }
        if provider_id:
            payload["provider_id"] = provider_id
        if model:
            payload["model"] = model
        if project_id:
            payload["project_id"] = project_id
        if max_iterations:
            payload["max_iterations"] = max_iterations
        if system_prompt:
            payload["system_prompt"] = system_prompt

        # Use longer timeout for agent operations
        timeout = httpx.Timeout(300.0, connect=10.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
            except httpx.HTTPStatusError as e:
                # Must read the response body before accessing .text in streaming mode
                await e.response.aread()
                logger.error(
                    f"Device control agent error: {e.response.status_code} - {e.response.text}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(f"Device control agent connection error: {e}")
                raise

    async def get_device_tools(
        self,
        device_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get available tools from a connected device."""
        return await self._request("GET", f"/v1/agent/devices/{device_id}/tools")

    async def list_connected_devices(self) -> Dict[str, Any]:
        """List all connected devices available for agent control."""
        return await self._request("GET", "/v1/agent/devices")


# Global singleton instance
device_control_client = DeviceControlClient()
