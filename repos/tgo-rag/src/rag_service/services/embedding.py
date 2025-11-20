"""
Embedding service for generating vector embeddings using multiple providers.

Supports:
- OpenAI embeddings (text-embedding-ada-002, text-embedding-3-small, etc.)
- Qwen3-Embedding (text-embedding-v4) via Alibaba Cloud DashScope
"""

import asyncio
from abc import abstractmethod
from enum import Enum
from typing import List, Optional
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    QWEN3 = "qwen3"
    OPENAI_COMPATIBLE = "openai_compatible"


class BaseEmbeddingClient(Embeddings):
    """Abstract base class for embedding clients."""

    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        pass
    async def aembed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        pass

    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        pass

    @abstractmethod
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        pass

    @abstractmethod
    def get_dimensions(self) -> int:
        """Get the embedding dimensions for this model."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name."""
        pass


class OpenAIEmbeddingClient(BaseEmbeddingClient):
    """OpenAI embedding client implementation."""

    def __init__(self, api_key: str, model: str, dimensions: int, batch_size: int = 100, base_url: Optional[str] = None):
        """
        Initialize OpenAI embedding client.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., text-embedding-ada-002)
            dimensions: Embedding dimensions
            batch_size: Batch size for processing
            base_url: Optional custom API base URL (for OpenAI-compatible endpoints)
        """
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

        # Compatibility mode: if base_url provided, try to pass through to LangChain; otherwise
        # fall back to using the official OpenAI SDK directly.
        self._compat_mode = False
        self._compat_client = None

        if base_url:
            self._compat_mode = True
            self._compat_client = OpenAI(api_key=api_key, base_url=base_url)
            self._client = None
            logger.info(f"Initialized OpenAI-compatible embedding client via OpenAI SDK with model: {model} at {base_url}")
                
        else:
            # Standard OpenAI embeddings via LangChain
            self._client = OpenAIEmbeddings(
                openai_api_key=api_key,
                model=model,
                chunk_size=batch_size,
            )
            logger.info(f"Initialized OpenAI embedding client with model: {model}")

    def _compat_make_embeddings_request(self, texts: List[str]) -> List[List[float]]:
        """Make embeddings request using OpenAI SDK for OpenAI-compatible endpoints."""
        try:
            if not self._compat_client:
                raise RuntimeError("Compatibility client not initialized")
            response = self._compat_client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
                encoding_format="float",
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"OpenAI-compatible embeddings request failed: {str(e)}")
            raise

    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        loop = asyncio.get_event_loop()
        if self._compat_mode:
            embeddings = await loop.run_in_executor(None, self._compat_make_embeddings_request, [text])
            if embeddings:
                return embeddings[0]
            raise ValueError("No embedding returned for query")
        return await loop.run_in_executor(None, self._client.embed_query, text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        loop = asyncio.get_event_loop()
        if self._compat_mode:
            all_embeddings = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                batch_embeddings = await loop.run_in_executor(
                    None,
                    self._compat_make_embeddings_request,
                    batch,
                )
                all_embeddings.extend(batch_embeddings)
            return all_embeddings
        return await loop.run_in_executor(None, self._client.embed_documents, texts)

    def get_dimensions(self) -> int:
        """Get the embedding dimensions for this model."""
        return self.dimensions

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model

    async def aembed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query (async interface)."""
        return await self.embed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents (async interface)."""
        return await self.embed_documents(texts)


class Qwen3EmbeddingClient(BaseEmbeddingClient):
    """Qwen3-Embedding client implementation using OpenAI client library."""

    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int, batch_size: int = 100):
        """
        Initialize Qwen3-Embedding client.

        Args:
            api_key: Alibaba Cloud DashScope API key
            base_url: API base URL (https://dashscope.aliyuncs.com/compatible-mode/v1)
            model: Model name (text-embedding-v4)
            dimensions: Embedding dimensions
            batch_size: Batch size for processing
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

        # Initialize OpenAI client with DashScope endpoint
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        logger.info(f"Initialized Qwen3-Embedding client with model: {model} at {base_url}")

    def _make_embeddings_request(self, texts: List[str]) -> List[List[float]]:
        """Make embeddings request using OpenAI client."""
        try:
            # Use OpenAI client to create embeddings
            response = self._client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
                encoding_format="float"
            )

            # Extract embeddings from response
            embeddings = []
            for item in response.data:
                embeddings.append(item.embedding)

            return embeddings

        except Exception as e:
            logger.error(f"OpenAI client embeddings request failed: {str(e)}")
            raise Exception(f"Qwen3 embeddings API request failed: {str(e)}")

    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        try:
            # Run synchronous OpenAI client call in thread pool
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                self._make_embeddings_request,
                [text]
            )

            if embeddings:
                logger.debug(f"Generated Qwen3 embedding for text of length {len(text)}")
                return embeddings[0]
            else:
                raise ValueError("No embedding returned for query")
        except Exception as e:
            logger.error(f"Failed to generate Qwen3 embedding for query: {str(e)}")
            raise

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        try:
            # Process in batches to respect API limits
            all_embeddings = []

            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]

                # Run synchronous OpenAI client call in thread pool
                loop = asyncio.get_event_loop()
                batch_embeddings = await loop.run_in_executor(
                    None,
                    self._make_embeddings_request,
                    batch
                )

                all_embeddings.extend(batch_embeddings)
                logger.debug(f"Generated Qwen3 embeddings for batch {i//self.batch_size + 1}")

            logger.debug(f"Generated Qwen3 embeddings for {len(texts)} documents")
            return all_embeddings
        except Exception as e:
            logger.error(f"Failed to generate Qwen3 embeddings for documents: {str(e)}")
            raise

    def get_dimensions(self) -> int:
        """Get the embedding dimensions for this model."""
        return self.dimensions

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model

    async def aembed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query (async interface)."""
        return await self.embed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents (async interface)."""
        return await self.embed_documents(texts)


class EmbeddingService:
    """Service for generating and managing vector embeddings with multiple provider support."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        batch_size: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize the embedding service.

        Args:
            provider: Override provider ("openai", "qwen3", or "openai_compatible"). If None, use global settings
            model: Override model name
            dimensions: Override embedding dimensions
            batch_size: Override embedding batch size
            api_key: Override provider API key
            base_url: Override provider base URL (for Qwen3 or openai_compatible)
        """
        self.settings = get_settings()
        self._embeddings_client: Optional[BaseEmbeddingClient] = None
        # Overrides (per-project)
        self._override_provider = provider.lower() if provider else None
        self._override_model = model
        self._override_dimensions = dimensions
        self._override_api_key = api_key
        self._override_base_url = base_url
        self._batch_size = batch_size if batch_size is not None else self.settings.embedding_batch_size
        # Effective provider
        effective_provider = self._override_provider or self.settings.embedding_provider.lower()
        self._provider = EmbeddingProvider(effective_provider)

    @property
    def embeddings_client(self) -> BaseEmbeddingClient:
        """Get or create the embeddings client based on configured provider."""
        if self._embeddings_client is None:
            self._embeddings_client = self._create_embedding_client()
        return self._embeddings_client

    def _create_embedding_client(self) -> BaseEmbeddingClient:
        """Create embedding client based on configured provider."""
        if self._provider == EmbeddingProvider.OPENAI:
            return self._create_openai_client()
        elif self._provider == EmbeddingProvider.QWEN3:
            return self._create_qwen3_client()
        elif self._provider == EmbeddingProvider.OPENAI_COMPATIBLE:
            return self._create_openai_compatible_client()
        else:
            raise ValueError(f"Unsupported embedding provider: {self._provider.value}")

    def _create_openai_client(self) -> OpenAIEmbeddingClient:
        """Create OpenAI embedding client (with per-project overrides if provided)."""
        api_key = self._override_api_key or self.settings.openai_api_key
        if not api_key:
            raise ValueError("OpenAI API key is required for OpenAI embedding generation")

        model = self._override_model or self.settings.embedding_model
        dimensions = self._override_dimensions or self.settings.embedding_dimensions
        batch_size = self._batch_size

        return OpenAIEmbeddingClient(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            batch_size=batch_size
        )

    def _create_qwen3_client(self) -> Qwen3EmbeddingClient:
        """Create Qwen3-Embedding client (with per-project overrides if provided)."""
        api_key = self._override_api_key or self.settings.qwen3_api_key
        if not api_key:
            raise ValueError("Qwen3 API key is required for Qwen3-Embedding generation")

        base_url = (self._override_base_url or self.settings.qwen3_base_url).rstrip('/')
        model = self._override_model or self.settings.qwen3_model
        dimensions = self._override_dimensions or self.settings.qwen3_dimensions
        batch_size = self._batch_size

        return Qwen3EmbeddingClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            dimensions=dimensions,
            batch_size=batch_size
        )

    def _create_openai_compatible_client(self) -> OpenAIEmbeddingClient:
        """Create OpenAI-compatible client (OpenAI SDK with custom base_url)."""
        api_key = self._override_api_key or self.settings.openai_api_key
        if not api_key:
            raise ValueError("OpenAI API key is required for openai_compatible embedding generation")

        base_url = (self._override_base_url or self.settings.openai_compatible_base_url or "").strip()
        if not base_url:
            raise ValueError("base_url is required for openai_compatible embedding generation")

        model = self._override_model or self.settings.embedding_model
        dimensions = self._override_dimensions or self.settings.embedding_dimensions
        batch_size = self._batch_size

        return OpenAIEmbeddingClient(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            batch_size=batch_size,
            base_url=base_url,
        )


    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to generate embedding for

        Returns:
            List of float values representing the embedding vector

        Raises:
            ValueError: If text is empty or API key is missing
            Exception: If embedding generation fails
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            embedding = await self.embeddings_client.embed_query(text)
            logger.debug(f"Generated embedding for text of length {len(text)} using {self._provider.value}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding using {self._provider.value}: {str(e)}")
            raise

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to generate embeddings for

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If texts list is empty
            Exception: If embedding generation fails
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        # Filter out empty texts
        non_empty_texts = [text for text in texts if text.strip()]
        if not non_empty_texts:
            raise ValueError("All texts are empty")

        try:
            # Process in batches to avoid API limits
            batch_size = self._batch_size
            all_embeddings = []

            for i in range(0, len(non_empty_texts), batch_size):
                batch = non_empty_texts[i:i + batch_size]
                batch_embeddings = await self.embeddings_client.embed_documents(batch)
                all_embeddings.extend(batch_embeddings)

                logger.debug(f"Generated embeddings for batch {i//batch_size + 1} using {self._provider.value}")

            logger.info(f"Generated {len(all_embeddings)} embeddings using {self._provider.value}")
            return all_embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings using {self._provider.value}: {str(e)}")
            raise

    def get_embedding_dimensions(self) -> int:
        """
        Get the dimensions of embeddings for the current model.

        Returns:
            Number of dimensions in the embedding vector
        """
        return self.embeddings_client.get_dimensions()

    def get_embedding_model(self) -> str:
        """
        Get the current embedding model name.

        Returns:
            Name of the embedding model
        """
        return self.embeddings_client.get_model_name()

    def get_embedding_provider(self) -> str:
        """
        Get the current embedding provider.

        Returns:
            Name of the embedding provider
        """
        return self._provider.value


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get the global embedding service instance.

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service



async def get_embedding_service_for_project(project_id) -> EmbeddingService:
    """Resolve and construct an EmbeddingService scoped to the given project.

    Looks up the active embedding configuration in rag_embedding_configs.
    Does NOT fall back to global configuration; missing/invalid config raises.
    """
    from sqlalchemy import select
    from ..database import get_db_session
    from ..models.embedding_config import EmbeddingConfig

    if project_id is None:
        raise ValueError("Project ID is required to resolve embedding configuration")

    # Query active config
    async with get_db_session() as db:
        result = await db.execute(
            select(EmbeddingConfig).where(
                EmbeddingConfig.project_id == project_id,
                EmbeddingConfig.is_active.is_(True),
            )
        )
        rec = result.scalar_one_or_none()

    if rec is None:
        raise ValueError(f"No active embedding configuration found for project {project_id}")

    provider = (rec.provider or "").lower()
    if provider == EmbeddingProvider.OPENAI.value:
        if not rec.api_key:
            raise ValueError(f"Project {project_id} embedding config missing OpenAI api_key")
        return EmbeddingService(
            provider="openai",
            model=rec.model,
            dimensions=rec.dimensions,
            batch_size=rec.batch_size,
            api_key=rec.api_key,
        )
    elif provider == EmbeddingProvider.QWEN3.value:
        if not rec.api_key:
            raise ValueError(f"Project {project_id} embedding config missing Qwen3 api_key")
        if not rec.base_url:
            raise ValueError(f"Project {project_id} embedding config missing Qwen3 base_url")
        return EmbeddingService(
            provider="qwen3",
            model=rec.model,
            dimensions=rec.dimensions,
            batch_size=rec.batch_size,
            api_key=rec.api_key,
            base_url=rec.base_url,
        )
    elif provider == EmbeddingProvider.OPENAI_COMPATIBLE.value:
        if not rec.api_key:
            raise ValueError(f"Project {project_id} embedding config missing OpenAI-compatible api_key")
        if not rec.base_url:
            raise ValueError(f"Project {project_id} embedding config missing OpenAI-compatible base_url")
        return EmbeddingService(
            provider="openai_compatible",
            model=rec.model,
            dimensions=rec.dimensions,
            batch_size=rec.batch_size,
            api_key=rec.api_key,
            base_url=rec.base_url,
        )

    else:
        return EmbeddingService(
            provider="openai",
            model=rec.model,
            dimensions=rec.dimensions,
            batch_size=rec.batch_size,
            api_key=rec.api_key,
            base_url=rec.base_url,
        )
