"""Local file system storage backend."""

import os
import shutil
from pathlib import Path
from typing import BinaryIO, Any
from urllib.parse import urlparse

from app.services.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Local file system storage implementation."""

    def __init__(self, base_path: str, api_base_url: str):
        """
        Initialize local storage backend.
        
        Args:
            base_path: Base directory for file storage
            api_base_url: Base URL for generating public URLs
        """
        self.base_path = Path(base_path)
        self.api_base_url = api_base_url.rstrip("/")
        self._ensure_base_path()

    def _ensure_base_path(self):
        """Ensure base storage directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: BinaryIO, path: str, content_type: str) -> str:
        """Upload file to local storage."""
        full_path = self.base_path / path.lstrip("/")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file synchronously (file uploads are already buffered)
        with open(full_path, "wb") as f:
            shutil.copyfileobj(file, f)
        
        return self.get_public_url(path)

    async def delete(self, path: str) -> bool:
        """Delete file from local storage."""
        full_path = self.base_path / path.lstrip("/")
        try:
            if full_path.exists():
                os.remove(full_path)
                return True
            return False
        except Exception:
            return False

    def get_public_url(self, path: str) -> str:
        """
        Get public URL for a file path.
        
        Handles both:
        - API paths: /v1/chat/files/{id}
        - Storage paths: chat/{project}/{id}/file.png
        """
        if path.startswith("/"):
            # Already an API path
            return f"{self.api_base_url}{path}"
        # Storage path - convert to API path
        return f"{self.api_base_url}/v1/chat/files/{path}"

    async def exists(self, path: str) -> bool:
        """Check if file exists in local storage."""
        full_path = self.base_path / path.lstrip("/")
        return full_path.exists()

    def resolve_url(self, url: str) -> str:
        """
        Resolve and normalize a possibly relative or incorrect public URL.
        """
        if not url or not isinstance(url, str):
            return url
        
        # If it's a relative path starting with /api, strip it for internal storage resolution
        path = url
        if path.startswith("/api/v1"):
            path = path[4:]
            
        if path.startswith("/"):
            # Relative path: /v1/chat/files/xxx
            return self.get_public_url(path)
            
        if url.startswith("http://") or url.startswith("https://"):
            # Full URL: Resolve ONLY if it points to localhost/127.0.0.1
            parsed = urlparse(url)
            if "localhost" in parsed.netloc or "127.0.0.1" in parsed.netloc:
                p = parsed.path
                if p.startswith("/api/v1"):
                    p = p[4:]
                return self.get_public_url(p)
                
        return url

    def get_file_access_url(self, file_id: str, storage_url: str) -> str:
        """
        For local storage, return API endpoint URL.
        Frontend accesses files via /v1/chat/files/{file_id}
        """
        return f"{self.api_base_url}/v1/chat/files/{file_id}"
