"""Tests for encryption utilities."""
from __future__ import annotations

import pytest

from app.core.encryption import encrypt_api_key, decrypt_api_key, SimpleEncryption


class TestEncryption:
    """Tests for SimpleEncryption class."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption are reversible."""
        original = "test-api-key-12345"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)

        assert decrypted == original

    def test_encrypt_produces_different_output(self):
        """Test that encrypted value differs from original."""
        original = "my-secret-key"
        encrypted = encrypt_api_key(original)

        assert encrypted != original

    def test_encrypt_empty_string(self):
        """Test encryption of empty string."""
        encrypted = encrypt_api_key("")
        assert encrypted == ""

        decrypted = decrypt_api_key("")
        assert decrypted == ""

    def test_encrypt_unicode(self):
        """Test encryption of unicode characters."""
        original = "密钥测试123"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)

        assert decrypted == original

    def test_encrypt_long_string(self):
        """Test encryption of long strings."""
        original = "a" * 1000
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)

        assert decrypted == original

    def test_singleton_instance(self):
        """Test that SimpleEncryption is a singleton."""
        instance1 = SimpleEncryption()
        instance2 = SimpleEncryption()

        assert instance1 is instance2

    def test_decrypt_invalid_base64(self):
        """Test decryption of invalid base64 returns original."""
        invalid = "not-valid-base64!!!"
        result = decrypt_api_key(invalid)

        # Should return original on failure
        assert result == invalid
