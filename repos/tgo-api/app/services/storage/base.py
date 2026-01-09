"""Storage backend abstraction for file storage."""

from abc import ABC, abstractmethod
from typing import BinaryIO, Optional


class StorageBackend(ABC):
    """Abstract base class for file storage backends."""

    @abstractmethod
    async def upload(self, file: BinaryIO, path: str, content_type: str) -> str:
        """
        Upload a file to storage.
        
        Args:
            file: File-like object to upload
            path: Relative path to store the file
            content_type: MIME type of the file
            
        Returns:
            Public URL to access the file
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            path: Relative path of the file to delete
            
        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    def get_public_url(self, path: str) -> str:
        """
        Get the public URL for a file path.
        
        Args:
            path: Relative path or API path (e.g., /v1/chat/files/{id})
            
        Returns:
            Full public URL to access the file
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if a file exists.
        
        Args:
            path: Relative path of the file
            
        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    def resolve_url(self, url: str) -> str:
        """
        Resolve and normalize a possibly relative or incorrect public URL.
        
        Args:
            url: The URL to resolve (relative path or absolute URL)
            
        Returns:
            A normalized absolute public URL
        """
        pass

    @abstractmethod
    def get_file_access_url(self, file_id: str, storage_url: str) -> str:
        """
        Get the URL that frontend should use to access the file.
        
        For local storage: returns API endpoint URL (/v1/chat/files/{file_id})
        For cloud storage: returns the direct storage URL
        
        Args:
            file_id: The database file ID
            storage_url: The URL returned by upload() method
            
        Returns:
            The URL that frontend should use to access the file
        """
        pass
