"""Device Control Service Client - HTTP client for tgo-device-control service."""

from typing import Any, Dict, Optional
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


# Global singleton instance
device_control_client = DeviceControlClient()
