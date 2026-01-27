"""Encryption utilities for sensitive data storage."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class SimpleEncryption:
    """Simple XOR-based encryption for API keys.

    This provides basic obfuscation for stored API keys. For production use
    with higher security requirements, consider using:
    - AWS KMS / Azure Key Vault / GCP KMS
    - HashiCorp Vault
    - cryptography.fernet.Fernet with proper key management

    The encryption key is derived from the TGO_ENCRYPTION_KEY environment variable.
    If not set, a default key based on the database URL is used (not recommended
    for production).
    """

    _instance: Optional["SimpleEncryption"] = None
    _key: Optional[bytes] = None

    def __new__(cls) -> "SimpleEncryption":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._key is not None:
            return

        # Try to get encryption key from environment
        env_key = os.getenv("TGO_ENCRYPTION_KEY")
        if env_key:
            # Use SHA-256 hash of the key for consistent length
            self._key = hashlib.sha256(env_key.encode()).digest()
            logger.info("Using encryption key from TGO_ENCRYPTION_KEY")
        else:
            # Fallback: derive key from database URL (not recommended for production)
            from app.core.config import settings
            fallback = settings.database_url or "default-fallback-key"
            self._key = hashlib.sha256(fallback.encode()).digest()
            logger.warning(
                "TGO_ENCRYPTION_KEY not set, using derived key. "
                "Set TGO_ENCRYPTION_KEY for production use."
            )

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string and return base64-encoded result.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""

        plaintext_bytes = plaintext.encode("utf-8")
        key = self._key or b""

        # XOR encryption with repeating key
        encrypted = bytes(
            pb ^ key[i % len(key)]
            for i, pb in enumerate(plaintext_bytes)
        )

        # Base64 encode for safe storage
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""

        try:
            encrypted = base64.b64decode(ciphertext.encode("utf-8"))
            key = self._key or b""

            # XOR decryption (same as encryption for XOR)
            decrypted = bytes(
                eb ^ key[i % len(key)]
                for i, eb in enumerate(encrypted)
            )

            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            # Return original value if decryption fails
            # (might be unencrypted legacy data)
            return ciphertext


# Singleton instance
_encryptor: Optional[SimpleEncryption] = None


def get_encryptor() -> SimpleEncryption:
    """Get the singleton encryptor instance."""
    global _encryptor
    if _encryptor is None:
        _encryptor = SimpleEncryption()
    return _encryptor


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage.

    Args:
        api_key: The API key to encrypt

    Returns:
        Encrypted API key (base64 encoded)
    """
    return get_encryptor().encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a stored API key.

    Args:
        encrypted_key: The encrypted API key (base64 encoded)

    Returns:
        Decrypted API key
    """
    return get_encryptor().decrypt(encrypted_key)
