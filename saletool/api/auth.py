"""Issue and verify JWT access tokens for the API (Bearer auth for the React SPA)."""

from __future__ import annotations

import logging
import os
import secrets
import time

import jwt

from saletool.db.factory import get_user_repository
from saletool.security import verify_password

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
EXPIRE_SECONDS = 12 * 3600  # 12 hours

_secret_key_cache: str | None = None


def _get_secret_key() -> str:
    """Read SALETOOL_SECRET_KEY; if unset, generate a process-local temporary key
    (tokens will expire when the server restarts)."""

    global _secret_key_cache
    if _secret_key_cache:
        return _secret_key_cache

    key = os.environ.get("SALETOOL_SECRET_KEY")
    if not key:
        key = secrets.token_hex(32)
        logger.warning(
            "SALETOOL_SECRET_KEY is not set; using a temporary key, so all "
            "tokens will expire when the server restarts. Set the "
            "SALETOOL_SECRET_KEY environment variable for stable sessions."
        )
    _secret_key_cache = key
    return key


def create_access_token(username: str) -> str:
    payload = {"sub": username, "exp": time.time() + EXPIRE_SECONDS}
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def authenticate(username: str, password: str) -> bool:
    repo = get_user_repository()
    stored_hash = repo.get_password_hash(username)
    if not stored_hash:
        return False
    return verify_password(password, stored_hash)
