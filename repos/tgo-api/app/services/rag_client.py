"""RAG service client for proxying requests to external RAG service."""

import json
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("rag_client")


class RAGServiceClient:
    """Client for communicating with the external RAG service."""
    
    def __init__(self):
        self.base_url = settings.RAG_SERVICE_URL.rstrip("/")
        self.timeout = settings.RAG_SERVICE_TIMEOUT
        self.api_key = settings.RAG_SERVICE_API_KEY
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for RAG service requests (no authentication)."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TGO-API-Service/0.1.0",
        }
        return headers

    def _get_multipart_headers(self) -> Dict[str, str]:
        """Get headers for multipart requests (no authentication)."""
        headers = {
            "User-Agent": "TGO-API-Service/0.1.0",
        }
        return headers

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make HTTP request to RAG service."""
        url = f"{self.base_url}{endpoint}"
        request_id = str(uuid4())

        # Choose appropriate headers based on request type
        if files:
            headers = self._get_multipart_headers()
        else:
            headers = self._get_headers()

        headers["X-Request-ID"] = request_id

        logger.info(
            f"RAG service request: {method} {url}",
            extra={
                "request_id": request_id,
                "method": method,
                "url": url,
                "has_files": bool(files),
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
                    files=files,
                    data=data,
                )
                
                logger.info(
                    f"RAG service response: {response.status_code}",
                    extra={
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds() if response.elapsed else None,
                    }
                )
                
                return response
                
        except httpx.TimeoutException as e:
            logger.error(
                f"RAG service timeout: {url}",
                extra={"request_id": request_id, "timeout": self.timeout}
            )
            raise HTTPException(
                status_code=504,
                detail="RAG service request timed out"
            )
        except httpx.RequestError as e:
            logger.error(
                f"RAG service request error: {e}",
                extra={"request_id": request_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to connect to RAG service"
            )
    
    async def _handle_response(self, response: httpx.Response) -> Any:
        """Handle RAG service response and convert errors."""
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
            f"RAG service error response: {response.status_code}",
            extra={
                "status_code": response.status_code,
                "error_data": error_data,
            }
        )
        
        raise HTTPException(
            status_code=response.status_code,
            detail=error_data
        )
    
    # Collection endpoints
    async def list_collections(
        self,
        project_id: str,
        display_name: Optional[str] = None,
        collection_type: Optional[str] = None,
        tags: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List collections from RAG service."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if display_name:
            params["display_name"] = display_name
        if collection_type:
            params["collection_type"] = collection_type
        if tags:
            params["tags"] = tags
        params["project_id"] = project_id

        response = await self._make_request(
            "GET", "/v1/collections", params=params
        )
        result = await self._handle_response(response)

        # Transform pagination field name for consistency with our schema
        if isinstance(result, dict) and "pagination" in result:
            pagination = result["pagination"]
            if "has_previous" in pagination:
                pagination["has_prev"] = pagination.pop("has_previous")

        return result
    
    async def create_collection(
        self,
        project_id: str,
        collection_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create collection in RAG service."""
        response = await self._make_request(
            "POST", "/v1/collections", json_data=collection_data, params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def get_collection(
        self,
        project_id: str,
        collection_id: str,
        include_stats: bool = False,
    ) -> Dict[str, Any]:
        """Get collection from RAG service."""
        params = {"include_stats": include_stats, "project_id": project_id}
        response = await self._make_request(
            "GET", f"/v1/collections/{collection_id}", params=params
        )
        return await self._handle_response(response)

    async def update_collection(
        self,
        project_id: str,
        collection_id: str,
        collection_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update collection in RAG service."""
        response = await self._make_request(
            "PUT", f"/v1/collections/{collection_id}", json_data=collection_data, params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def delete_collection(
        self,
        project_id: str,
        collection_id: str,
    ) -> None:
        """Delete collection from RAG service."""
        response = await self._make_request(
            "DELETE", f"/v1/collections/{collection_id}", params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def search_collection_documents(
        self,
        project_id: str,
        collection_id: str,
        search_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Search documents in collection."""
        response = await self._make_request(
            "POST", f"/v1/collections/{collection_id}/documents/search",
            json_data=search_data, params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def list_collection_crawl_jobs(
        self,
        project_id: str,
        collection_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List crawl jobs for a website collection."""
        params: Dict[str, Any] = {
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = status

        response = await self._make_request(
            "GET", f"/v1/collections/{collection_id}/crawl-jobs", params=params
        )
        result = await self._handle_response(response)

        # Transform pagination field name for consistency
        if isinstance(result, dict) and "pagination" in result:
            pagination = result["pagination"]
            if "has_previous" in pagination:
                pagination["has_prev"] = pagination.pop("has_previous")

        return result

    async def list_collection_pages(
        self,
        project_id: str,
        collection_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List crawled pages for a website collection."""
        params: Dict[str, Any] = {
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = status

        response = await self._make_request(
            "GET", f"/v1/collections/{collection_id}/pages", params=params
        )
        result = await self._handle_response(response)

        # Transform pagination field name for consistency
        if isinstance(result, dict) and "pagination" in result:
            pagination = result["pagination"]
            if "has_previous" in pagination:
                pagination["has_prev"] = pagination.pop("has_previous")

        return result

    # File endpoints
    async def list_files(
        self,
        project_id: str,
        collection_id: Optional[str] = None,
        status: Optional[str] = None,
        content_type: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        tags: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List files from RAG service."""
        params = {"limit": limit, "offset": offset}
        if collection_id:
            params["collection_id"] = collection_id
        if status:
            params["status"] = status
        if content_type:
            params["content_type"] = content_type
        if uploaded_by:
            params["uploaded_by"] = uploaded_by
        if tags:
            params["tags"] = tags
        params["project_id"] = project_id

        response = await self._make_request(
            "GET", "/v1/files", params=params
        )
        result = await self._handle_response(response)

        # Transform pagination field name for consistency with our schema
        if isinstance(result, dict) and "pagination" in result:
            pagination = result["pagination"]
            if "has_previous" in pagination:
                pagination["has_prev"] = pagination.pop("has_previous")

        return result
    
    async def upload_file(
        self,
        project_id: str,
        file: UploadFile,
        collection_id: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload file to RAG service."""
        files = {"file": (file.filename, file.file, file.content_type)}
        data = {"project_id": project_id}

        if collection_id:
            data["collection_id"] = collection_id
        if description:
            data["description"] = description
        if language:
            data["language"] = language
        if tags:
            data["tags"] = tags

        response = await self._make_request(
            "POST", "/v1/files", files=files, data=data
        )
        return await self._handle_response(response)

    async def get_file(
        self,
        project_id: str,
        file_id: str,
    ) -> Dict[str, Any]:
        """Get file from RAG service."""
        response = await self._make_request(
            "GET", f"/v1/files/{file_id}", params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def download_file(
        self,
        project_id: str,
        file_id: str,
    ) -> httpx.Response:
        """Download file from RAG service and return raw response for streaming."""
        url = f"{self.base_url}/v1/files/{file_id}/download"
        request_id = str(uuid4())

        headers = self._get_headers()
        headers["X-Request-ID"] = request_id

        logger.info(
            f"RAG service file download: GET {url}",
            extra={
                "request_id": request_id,
                "file_id": file_id,
                "url": url,
            }
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url=url,
                    headers=headers,
                    params={"project_id": project_id},
                )

                logger.info(
                    f"RAG service download response: {response.status_code}",
                    extra={
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "content_type": response.headers.get("content-type"),
                        "content_length": response.headers.get("content-length"),
                        "response_time": response.elapsed.total_seconds() if response.elapsed else None,
                    }
                )

                # Return the raw response for streaming (don't call _handle_response)
                return response

        except httpx.TimeoutException as e:
            logger.error(
                f"RAG service download timeout: {url}",
                extra={"request_id": request_id, "timeout": self.timeout}
            )
            raise HTTPException(
                status_code=504,
                detail="RAG service download request timed out"
            )
        except httpx.RequestError as e:
            logger.error(
                f"RAG service download request error: {e}",
                extra={"request_id": request_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to connect to RAG service for file download"
            )

    async def delete_file(
        self,
        project_id: str,
        file_id: str,
    ) -> None:
        """Delete file from RAG service."""
        response = await self._make_request(
            "DELETE", f"/v1/files/{file_id}", params={"project_id": project_id}
        )
        return await self._handle_response(response)

    async def upload_files_batch(
        self,
        project_id: str,
        files: List[UploadFile],
        collection_id: str,
        description: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload multiple files to RAG service in a batch."""
        # Prepare files for multipart upload
        files_data = []
        for file in files:
            files_data.append(("files", (file.filename, file.file, file.content_type)))

        data = {"collection_id": collection_id, "project_id": project_id}

        if description:
            data["description"] = description
        if language:
            data["language"] = language
        if tags:
            data["tags"] = tags

        response = await self._make_request(
            "POST", "/v1/files/batch", files=files_data, data=data
        )
        return await self._handle_response(response)

    # Website Crawl endpoints
    async def list_crawl_jobs(
        self,
        project_id: str,
        collection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List website crawl jobs from RAG service."""
        params: Dict[str, Any] = {
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        }
        if collection_id:
            params["collection_id"] = collection_id
        if status:
            params["status"] = status

        response = await self._make_request("GET", "/v1/websites/crawl", params=params)
        result = await self._handle_response(response)

        # Transform pagination field name for consistency
        if isinstance(result, dict) and "pagination" in result:
            pagination = result["pagination"]
            if "has_previous" in pagination:
                pagination["has_prev"] = pagination.pop("has_previous")

        return result

    async def create_crawl_job(
        self,
        project_id: str,
        collection_id: str,
        crawl_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new website crawl job."""
        params = {"project_id": project_id, "collection_id": collection_id}
        response = await self._make_request(
            "POST", "/v1/websites/crawl", json_data=crawl_data, params=params
        )
        return await self._handle_response(response)

    async def get_crawl_job(
        self,
        project_id: str,
        job_id: str,
    ) -> Dict[str, Any]:
        """Get a specific crawl job."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "GET", f"/v1/websites/crawl/{job_id}", params=params
        )
        return await self._handle_response(response)

    async def delete_crawl_job(
        self,
        project_id: str,
        job_id: str,
    ) -> None:
        """Delete a crawl job and all associated pages."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "DELETE", f"/v1/websites/crawl/{job_id}", params=params
        )
        await self._handle_response(response)

    async def cancel_crawl_job(
        self,
        project_id: str,
        job_id: str,
    ) -> Dict[str, Any]:
        """Cancel a running crawl job."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/websites/crawl/{job_id}/cancel", params=params
        )
        return await self._handle_response(response)

    async def list_crawl_pages(
        self,
        project_id: str,
        job_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List pages crawled for a specific job."""
        params: Dict[str, Any] = {
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = status

        response = await self._make_request(
            "GET", f"/v1/websites/crawl/{job_id}/pages", params=params
        )
        result = await self._handle_response(response)

        # Transform pagination field name for consistency
        if isinstance(result, dict) and "pagination" in result:
            pagination = result["pagination"]
            if "has_previous" in pagination:
                pagination["has_prev"] = pagination.pop("has_previous")

        return result

    async def add_page_to_crawl_job(
        self,
        project_id: str,
        job_id: str,
        url: str,
    ) -> Dict[str, Any]:
        """Add a single page URL to an existing crawl job."""
        params = {"project_id": project_id}
        json_data = {"url": url}
        response = await self._make_request(
            "POST", f"/v1/websites/crawl/{job_id}/pages",
            params=params,
            json_data=json_data
        )
        return await self._handle_response(response)

    async def crawl_deeper_from_page(
        self,
        project_id: str,
        page_id: str,
        crawl_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract links from an existing page and add them to the crawl queue."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/websites/pages/{page_id}/crawl-deeper",
            params=params,
            json_data=crawl_data
        )
        return await self._handle_response(response)

    # QA Pairs endpoints
    async def create_qa_pair(
        self,
        project_id: str,
        collection_id: str,
        qa_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a single QA pair in a collection."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/collections/{collection_id}/qa-pairs",
            params=params,
            json_data=qa_data
        )
        return await self._handle_response(response)

    async def list_qa_pairs(
        self,
        project_id: str,
        collection_id: str,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List QA pairs in a collection."""
        params: Dict[str, Any] = {
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        }
        if category:
            params["category"] = category
        if status:
            params["status"] = status

        response = await self._make_request(
            "GET", f"/v1/collections/{collection_id}/qa-pairs", params=params
        )
        return await self._handle_response(response)

    async def batch_create_qa_pairs(
        self,
        project_id: str,
        collection_id: str,
        qa_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Batch create QA pairs in a collection."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/collections/{collection_id}/qa-pairs/batch",
            params=params,
            json_data=qa_data
        )
        return await self._handle_response(response)

    async def import_qa_pairs(
        self,
        project_id: str,
        collection_id: str,
        import_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Import QA pairs from JSON/CSV."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "POST", f"/v1/collections/{collection_id}/qa-pairs/import",
            params=params,
            json_data=import_data
        )
        return await self._handle_response(response)

    async def get_qa_pair(
        self,
        project_id: str,
        qa_pair_id: str,
    ) -> Dict[str, Any]:
        """Get a single QA pair by ID."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "GET", f"/v1/qa-pairs/{qa_pair_id}", params=params
        )
        return await self._handle_response(response)

    async def update_qa_pair(
        self,
        project_id: str,
        qa_pair_id: str,
        qa_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a QA pair."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "PUT", f"/v1/qa-pairs/{qa_pair_id}",
            params=params,
            json_data=qa_data
        )
        return await self._handle_response(response)

    async def delete_qa_pair(
        self,
        project_id: str,
        qa_pair_id: str,
    ) -> None:
        """Delete a QA pair."""
        params = {"project_id": project_id}
        response = await self._make_request(
            "DELETE", f"/v1/qa-pairs/{qa_pair_id}", params=params
        )
        await self._handle_response(response)


# Global RAG client instance
rag_client = RAGServiceClient()