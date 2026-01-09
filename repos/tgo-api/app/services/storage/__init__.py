"""Storage services module.

Provides a unified interface for file storage.
Currently only supports local storage, OSS can be added later.
"""

from app.core.config import settings
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorageBackend


def get_storage_backend() -> StorageBackend:
    """
    Factory function to get the configured storage backend.
    """
    storage_type = getattr(settings, "STORAGE_TYPE", "local").lower()
    
    if storage_type == "oss":
        from app.services.storage.aliyun_oss import AliyunOSSBackend
        return AliyunOSSBackend(
            endpoint=settings.OSS_ENDPOINT,
            bucket_name=settings.OSS_BUCKET_NAME,
            access_key_id=settings.OSS_ACCESS_KEY_ID,
            access_key_secret=settings.OSS_ACCESS_KEY_SECRET,
            bucket_url=settings.OSS_BUCKET_URL,
        )
    elif storage_type == "minio":
        from app.services.storage.minio import MinIOBackend
        return MinIOBackend(
            endpoint_url=settings.MINIO_URL,
            access_key_id=settings.MINIO_ACCESS_KEY_ID,
            secret_access_key=settings.MINIO_SECRET_ACCESS_KEY,
            bucket_name=settings.MINIO_BUCKET_NAME,
            upload_url=settings.MINIO_UPLOAD_URL,
            download_url=settings.MINIO_DOWNLOAD_URL,
        )
    
    # Default to local storage
    return LocalStorageBackend(
        base_path=getattr(settings, "UPLOAD_DIR", "./uploads"),
        api_base_url=settings.API_BASE_URL,
    )


# Global storage instance (lazy initialization)
_storage = None


def get_storage() -> StorageBackend:
    """Get the global storage backend instance."""
    global _storage
    if _storage is None:
        _storage = get_storage_backend()
    return _storage


__all__ = [
    "StorageBackend",
    "LocalStorageBackend",
    "get_storage_backend",
    "get_storage",
]
