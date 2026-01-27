"""Base LLM client that handles provider configuration and API calls.

This module provides the foundation for both reasoning and vision model clients,
with support for multiple LLM providers (OpenAI, Anthropic, Dashscope, Azure).
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# Provider type aliases for matching
OPENAI_PROVIDERS = ("openai", "gpt", "gpt-4o", "oai")
ANTHROPIC_PROVIDERS = ("anthropic", "claude")
DASHSCOPE_PROVIDERS = ("dashscope", "ali", "aliyun", "qwen")
AZURE_PROVIDERS = ("azure_openai", "azure-openai", "azure")

# Default base URLs
DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com/v1"
DEFAULT_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass
class ProviderConfig:
    """Provider configuration fetched from tgo-api."""

    provider_type: str
    api_key: str
    api_base_url: Optional[str] = None
    config: Optional[dict[str, Any]] = None


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    model: str
    usage: dict[str, int]
    raw_response: dict[str, Any]

    @classmethod
    def from_openai_format(cls, response: dict[str, Any], model_id: str) -> "LLMResponse":
        """Create from OpenAI-format response."""
        content = ""
        if "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"].get("content", "")

        return cls(
            content=content,
            model=response.get("model", model_id),
            usage=response.get("usage", {}),
            raw_response=response,
        )


class BaseLLMClient:
    """Base LLM client for calling various LLM providers.

    This client:
    1. Fetches provider configuration from tgo-api's internal API (on-demand)
    2. Routes calls to the appropriate provider-specific method
    3. Supports OpenAI, Anthropic, Dashscope, and Azure OpenAI
    """

    def __init__(
        self,
        provider_id: str,
        model_id: str,
        api_internal_url: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """Initialize the LLM client.

        Args:
            provider_id: AI Provider ID from tgo-api
            model_id: Model identifier (e.g., "gpt-4o", "qwen-plus")
            api_internal_url: TGO API internal service URL
            timeout: Request timeout in seconds
        """
        self.provider_id = provider_id
        self.model_id = model_id
        self.api_internal_url = api_internal_url or settings.api_internal_url
        self.timeout = timeout
        self._config_cache: Optional[ProviderConfig] = None

    async def _get_config(self) -> ProviderConfig:
        """Fetch provider configuration from tgo-api internal API.

        Returns:
            ProviderConfig with decrypted API key and settings
        """
        if self._config_cache:
            return self._config_cache

        url = f"{self.api_internal_url}/internal/ai-providers/{self.provider_id}/config"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                self._config_cache = ProviderConfig(
                    provider_type=data["provider_type"],
                    api_key=data["api_key"],
                    api_base_url=data.get("api_base_url"),
                    config=data.get("config"),
                )
                return self._config_cache

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Failed to fetch provider config: {e.response.status_code} - {url} "
                    f"{e.response.text}"
                )
                raise ValueError(f"Failed to fetch provider config: {e.response.text}")
            except Exception as e:
                logger.error(f"Failed to fetch provider config: {e} - {url}")
                raise

    def _get_provider_type(self, config: ProviderConfig) -> str:
        """Determine the provider type category."""
        provider_type = config.provider_type.lower()

        if provider_type in ANTHROPIC_PROVIDERS:
            return "anthropic"
        elif provider_type in AZURE_PROVIDERS:
            return "azure"
        elif provider_type in DASHSCOPE_PROVIDERS:
            return "dashscope"
        else:
            return "openai"  # Default to OpenAI-compatible

    def _get_base_url(self, config: ProviderConfig) -> str:
        """Get the API base URL for the provider."""
        if config.api_base_url:
            return config.api_base_url.rstrip("/")

        provider_category = self._get_provider_type(config)
        if provider_category == "anthropic":
            return DEFAULT_ANTHROPIC_BASE
        elif provider_category == "dashscope":
            return DEFAULT_DASHSCOPE_BASE
        else:
            return DEFAULT_OPENAI_BASE

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        json_response: bool = True,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Call the LLM with the given messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            json_response: Whether to request JSON output format
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse with parsed content
        """
        config = await self._get_config()
        provider_category = self._get_provider_type(config)

        logger.debug(f"Calling LLM provider: {provider_category}, model: {self.model_id}")

        try:
            if provider_category == "anthropic":
                result = await self._call_anthropic(config, messages, json_response, max_tokens)
            elif provider_category == "azure":
                result = await self._call_azure(config, messages, json_response, max_tokens)
            else:
                result = await self._call_openai_compatible(config, messages, json_response, max_tokens)

            response = LLMResponse.from_openai_format(result, self.model_id)
            logger.debug(f"LLM call completed, tokens: {response.usage}")
            return response

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API request failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def _call_openai_compatible(
        self,
        config: ProviderConfig,
        messages: list[dict[str, Any]],
        json_response: bool,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call OpenAI-compatible API (OpenAI, Dashscope, etc.)."""
        base_url = self._get_base_url(config)

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if json_response:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _call_anthropic(
        self,
        config: ProviderConfig,
        messages: list[dict[str, Any]],
        json_response: bool,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call Anthropic Claude API."""
        base_url = self._get_base_url(config)
        extra_config = config.config or {}
        anthropic_version = extra_config.get("anthropic_version", "2023-06-01")

        # Convert messages to Anthropic format
        anthropic_messages = self._convert_to_anthropic_format(messages)

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
        }

        if json_response:
            payload["system"] = "You must respond with valid JSON only. No other text."

        headers = {
            "x-api-key": config.api_key,
            "anthropic-version": anthropic_version,
            "Content-Type": "application/json",
        }

        url = f"{base_url}/messages"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

        # Convert to OpenAI format
        return self._convert_anthropic_response(result)

    async def _call_azure(
        self,
        config: ProviderConfig,
        messages: list[dict[str, Any]],
        json_response: bool,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call Azure OpenAI API."""
        base_url = self._get_base_url(config)
        extra_config = config.config or {}
        api_version = extra_config.get("api_version", "2024-02-15-preview")

        if not config.api_base_url:
            raise ValueError("api_base_url is required for Azure OpenAI")

        if "/openai" not in base_url:
            base_url = f"{base_url}/openai"

        payload: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if json_response:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "api-key": config.api_key,
            "Content-Type": "application/json",
        }

        url = f"{base_url}/deployments/{self.model_id}/chat/completions?api-version={api_version}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _convert_to_anthropic_format(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert OpenAI-format messages to Anthropic format."""
        anthropic_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Skip system messages (handled separately in Anthropic)
            if role == "system":
                continue

            # Handle string content
            if isinstance(content, str):
                anthropic_messages.append({
                    "role": role,
                    "content": [{"type": "text", "text": content}]
                })
            # Handle array content (multimodal)
            elif isinstance(content, list):
                anthropic_content = []
                for item in content:
                    if item.get("type") == "text":
                        anthropic_content.append({
                            "type": "text",
                            "text": item.get("text", "")
                        })
                    elif item.get("type") == "image_url":
                        # Convert image URL to Anthropic format
                        image_url = item.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:"):
                            # Parse data URL
                            parts = image_url.split(",", 1)
                            if len(parts) == 2:
                                media_info = parts[0]  # e.g., "data:image/png;base64"
                                media_type = media_info.split(":")[1].split(";")[0]
                                image_data = parts[1]
                                anthropic_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_data,
                                    }
                                })

                anthropic_messages.append({
                    "role": role,
                    "content": anthropic_content
                })

        return anthropic_messages

    def _convert_anthropic_response(self, result: dict[str, Any]) -> dict[str, Any]:
        """Convert Anthropic response to OpenAI format."""
        content = ""
        if result.get("content"):
            for block in result["content"]:
                if block.get("type") == "text":
                    content += block.get("text", "")

        return {
            "id": result.get("id", ""),
            "object": "chat.completion",
            "model": result.get("model", self.model_id),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": result.get("stop_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
                "total_tokens": (
                    result.get("usage", {}).get("input_tokens", 0)
                    + result.get("usage", {}).get("output_tokens", 0)
                ),
            },
        }

    @staticmethod
    def _prepare_image_data(image: bytes | str) -> tuple[str, str]:
        """Prepare image data for API calls.

        Args:
            image: Image bytes or base64 encoded string

        Returns:
            Tuple of (base64_data, image_type)
        """
        if isinstance(image, str):
            image_base64 = image
            try:
                image_bytes = base64.b64decode(image)
            except Exception:
                image_bytes = b""
        else:
            image_base64 = base64.b64encode(image).decode("utf-8")
            image_bytes = image

        # Detect image type
        image_type = "png"
        if image_bytes.startswith(b"\x89PNG"):
            image_type = "png"
        elif image_bytes.startswith(b"\xff\xd8"):
            image_type = "jpeg"
        elif image_bytes.startswith(b"GIF8"):
            image_type = "gif"
        elif image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:12]:
            image_type = "webp"

        return image_base64, image_type

    @staticmethod
    def parse_json_response(content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks.

        Args:
            content: Raw response content

        Returns:
            Parsed JSON dictionary
        """
        if not content:
            return {}

        content = content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            # First try standard json.loads
            return json.loads(content)
        except json.JSONDecodeError:
            # If it fails, try to find JSON-like structure within the content
            # This handles cases where LLM might include extra text before/after JSON
            import re
            json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            logger.error(f"Failed to parse JSON response: {content[:200]}")
            raise ValueError(f"Invalid JSON response: {content[:100]}")
