import httpx
from typing import Any, Dict, Optional, List
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.store import StoreModelDetail

logger = get_logger("store_client")

class StoreClient:
    """Client for interacting with the Store API (Tools and Models)."""

    def __init__(self):
        self.base_url = f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1"
        self.timeout = settings.STORE_TIMEOUT

    async def get_tool(self, tool_id: str, api_key: str) -> Dict[str, Any]:
        """Fetch tool details from Store."""
        url = f"{self.base_url}/tools/{tool_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers={"X-API-Key": api_key}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Store API error (tools): {e.response.status_code} {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Store connection error: {str(e)}")
                raise

    async def install_tool(self, tool_id: str, api_key: str) -> Dict[str, Any]:
        """Mark tool as installed in Store."""
        url = f"{self.base_url}/install/tool/{tool_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers={"X-API-Key": api_key}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Store API error (install tool): {e.response.status_code} {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Store connection error: {str(e)}")
                raise

    async def uninstall_tool(self, tool_id: str, api_key: str) -> Dict[str, Any]:
        """Mark tool as uninstalled in Store."""
        url = f"{self.base_url}/install/tool/{tool_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    "DELETE",
                    url,
                    headers={"X-API-Key": api_key}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Store API error (uninstall tool): {e.response.status_code} {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Store connection error: {str(e)}")
                raise

    async def get_model(self, model_id: str, api_key: str) -> StoreModelDetail:
        """Fetch model details from Store."""
        url = f"{self.base_url}/models/{model_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers={"X-API-Key": api_key}
                )
                response.raise_for_status()
                return StoreModelDetail.model_validate(response.json())
            except httpx.HTTPStatusError as e:
                logger.error(f"Store API error (models): {e.response.status_code} {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Store connection error: {str(e)}")
                raise

    async def install_model(self, model_id: str, api_key: str) -> Dict[str, Any]:
        """Mark model as installed in Store."""
        url = f"{self.base_url}/install/model/{model_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers={"X-API-Key": api_key}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Store API error (install model): {e.response.status_code} {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Store connection error: {str(e)}")
                raise

    async def uninstall_model(self, model_id: str, api_key: str) -> Dict[str, Any]:
        """Mark model as uninstalled in Store."""
        url = f"{self.base_url}/install/model/{model_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    "DELETE",
                    url,
                    headers={"X-API-Key": api_key}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Store API error (uninstall model): {e.response.status_code} {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Store connection error: {str(e)}")
                raise

    async def get_api_key(self, access_token: str) -> Dict[str, Any]:
        """Fetch user's API key from Store using access token."""
        url = f"{self.base_url}/auth/api-key"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Store API error (auth): {e.response.status_code} {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Store connection error: {str(e)}")
                raise

store_client = StoreClient()
