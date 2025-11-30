"""
FastAPI routers for the RAG service.
"""

from . import collections, files, health, monitoring, embedding_config, websites, qa

__all__ = [
    "collections",
    "files",
    "health",
    "monitoring",
    "embedding_config",
    "websites",
    "qa",
]
