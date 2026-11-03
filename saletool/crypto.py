"""Encrypt sensitive values (API keys) before storing them in the database.

Protection scope, to avoid misunderstandings: this protects against **accidental
exposure** (a database file committed by mistake, a copied backup, or someone
opening the .db file in a SQLite viewer). It does **not** protect against a
compromised server, because the decryption key derived from SALETOOL_SECRET_KEY
is on that machine.

The key is derived from SALETOOL_SECRET_KEY using HKDF. Changing the secret key
makes all existing encrypted values unreadable, so users must enter their API
keys again.
"""

from __future__ import annotations

import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"
_INFO = b"saletool-settings-encryption-v1"


def _fernet() -> Fernet:
    secret = os.environ.get("SALETOOL_SECRET_KEY")
    if not secret:
        # Do not generate a random key here: every restart would create a new key
        # and make all saved API keys unreadable.
        raise RuntimeError(
            "Set SALETOOL_SECRET_KEY to store API keys securely. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_INFO,
    ).derive(secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt(value: str | None) -> str | None:
    """Encrypt a string. Return None if the input is empty."""
    if not value:
        return None
    if value.startswith(_PREFIX):
        return value  # Already encrypted; avoid encrypting twice.
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt(value: str | None) -> str | None:
    """Decrypt a value. Return None if empty or unreadable (e.g. after a secret key change)."""
    if not value:
        return None
    if not value.startswith(_PREFIX):
        # Value was stored before encryption was enabled; return it as-is for migration on save.
        return value

    token = value[len(_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, RuntimeError):
        logger.warning(
            "Could not decrypt the saved value; SALETOOL_SECRET_KEY may have changed. "
            "The user must re-enter the API key in Settings."
        )
        return None


def mask(value: str | None) -> str | None:
    """Create a safe display value for the frontend, revealing only the last four characters."""
    if not value:
        return None
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * 8 + value[-4:]
