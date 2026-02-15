"""API key encryption/decryption using Fernet symmetric encryption."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create a Fernet instance derived from SECRET_KEY env var."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    secret_key = os.getenv("SECRET_KEY", "")
    if not secret_key:
        raise ValueError(
            "SECRET_KEY environment variable is not set. "
            "This is required for API key encryption."
        )

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        secret_key.encode("utf-8"),
        b"trpg-world-llm-settings-salt",
        iterations=100_000,
        dklen=32,
    )
    fernet_key = base64.urlsafe_b64encode(derived_key)
    _fernet_instance = Fernet(fernet_key)
    return _fernet_instance


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt an API key string. Returns base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plain_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key string from base64-encoded ciphertext."""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode("utf-8")).decode("utf-8")
