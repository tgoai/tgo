"""Workflow service client for proxying requests to internal Workflow service."""

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("workflow_client")


class WorkflowServiceClient:
    """Client for communicating with the internal Workflow service."""
    
    def __init__(self):
        self.base_url = settings.WORKFLOW_SERVICE_URL.rstrip("/")
        self.timeout = settings.WORKFLOW_SERVICE_TIMEOUT
        self.api_key = settings.WORKFLOW_SERVICE_API_KEY
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Workflow service requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TGO-API-Service/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make HTTP request to Workflow service."""
        url = f"{self.base_url}{endpoint}"
        request_id = str(uuid4())
        headers = self._get_headers()
        headers["X-Request-ID"] = request_id

        logger.info(
            f"Workflow service request: {method} {url}",
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
                    json=json_data,
                    params=params,
                )
                
                logger.info(
                    f"Workflow service response: {response.status_code}",
                    extra={
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds() if response.elapsed else None,
                    }
                )
                
                return response
                
        except httpx.TimeoutException as e:
            logger.error(f"Workflow service timeout: {url}")
            raise HTTPException(status_code=504, detail="Workflow service request timed out")
        except httpx.RequestError as e:
            logger.error(f"Workflow service request error: {e}")
            raise HTTPException(status_code=502, detail="Failed to connect to Workflow service")
    
    async def _handle_response(self, response: httpx.Response) -> Any:
        """Handle Workflow service response and convert errors."""
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
        
        raise HTTPException(
            status_code=response.status_code,
            detail=error_data
        )

    # Workflow endpoints (aligned with Workflow service OpenAPI: /v1/...)
    async def list_workflows(
        self,
        project_id: str,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "project_id": project_id,
            "skip": skip,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        if status is not None:
            params["status"] = status
        if search is not None:
            params["search"] = search
        if tags is not None:
            params["tags"] = tags
        response = await self._make_request("GET", "/v1/workflows/", params=params)
        return await self._handle_response(response)

    async def create_workflow(
        self, project_id: str, workflow_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", "/v1/workflows/", json_data=workflow_data, params=params
        )
        return await self._handle_response(response)

    async def get_workflow(self, workflow_id: str, project_id: str) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "GET", f"/v1/workflows/{workflow_id}", params=params
        )
        return await self._handle_response(response)

    async def update_workflow(
        self, workflow_id: str, project_id: str, workflow_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "PUT", f"/v1/workflows/{workflow_id}", json_data=workflow_data, params=params
        )
        return await self._handle_response(response)

    async def delete_workflow(self, workflow_id: str, project_id: str) -> None:
        params = {"project_id": project_id}
        response = await self._make_request(
            "DELETE", f"/v1/workflows/{workflow_id}", params=params
        )
        await self._handle_response(response)

    async def duplicate_workflow(
        self,
        workflow_id: str,
        project_id: str,
        request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST",
            f"/v1/workflows/{workflow_id}/duplicate",
            json_data=request,
            params=params,
        )
        return await self._handle_response(response)

    async def validate_workflow_generic(
        self, project_id: str, request: Dict[str, Any]
    ) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", "/v1/workflows/validate", json_data=request, params=params
        )
        return await self._handle_response(response)

    async def validate_workflow(self, workflow_id: str, project_id: str) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/workflows/{workflow_id}/validate", params=params
        )
        return await self._handle_response(response)

    async def publish_workflow(self, workflow_id: str, project_id: str) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/workflows/{workflow_id}/publish", params=params
        )
        return await self._handle_response(response)

    async def get_workflow_variables(
        self, workflow_id: str, project_id: str
    ) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "GET", f"/v1/workflows/{workflow_id}/variables", params=params
        )
        return await self._handle_response(response)

    async def execute_workflow(
        self, workflow_id: str, project_id: str, request: Dict[str, Any]
    ) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST",
            f"/v1/workflows/{workflow_id}/execute",
            json_data=request,
            params=params,
        )
        return await self._handle_response(response)

    async def get_execution(self, execution_id: str, project_id: str) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "GET", f"/v1/workflows/executions/{execution_id}", params=params
        )
        return await self._handle_response(response)

    async def list_workflow_executions(
        self, workflow_id: str, project_id: str, skip: int = 0, limit: int = 20
    ) -> List[Dict[str, Any]]:
        params = {"project_id": project_id, "skip": skip, "limit": limit}
        response = await self._make_request(
            "GET", f"/v1/workflows/{workflow_id}/executions", params=params
        )
        return await self._handle_response(response)

    async def cancel_execution(self, execution_id: str, project_id: str) -> Dict[str, Any]:
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/workflows/executions/{execution_id}/cancel", params=params
        )
        return await self._handle_response(response)

    async def execute_workflow_stream(
        self, workflow_id: str, project_id: str, request: Dict[str, Any]
    ):
        """Execute workflow with streaming response (SSE)."""
        url = f"{self.base_url}/v1/workflows/{workflow_id}/execute/stream"
        params = {"project_id": project_id}
        headers = self._get_headers()
        headers["X-Request-ID"] = str(uuid4())

        async def stream_generator():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", url, json=request, params=params, headers=headers
                ) as response:
                    if not response.is_success:
                        # For simplicity, if error occurs before stream starts, we'll just yield it as a pseudo-event or let it raise
                        # But better to handle it properly in the endpoint
                        await response.aread()
                        try:
                            error_detail = response.json()
                        except:
                            error_detail = response.text
                        raise HTTPException(
                            status_code=response.status_code, detail=error_detail
                        )

                    async for line in response.aiter_lines():
                        if line:
                            yield f"{line}\n\n"

        return stream_generator()


# Global workflow client instance
workflow_client = WorkflowServiceClient()

