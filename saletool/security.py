"""Hash and verify passwords (stdlib only; no external dependencies).

Uses PBKDF2-HMAC-SHA256. It is not the strongest available option (bcrypt/argon2),
but is suitable for an internal tool and avoids native compiled extensions.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_SCHEME = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_SCHEME}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_str, salt_hex, digest_hex = encoded.split("$")
    except ValueError:
        return False
    if scheme != _SCHEME:
        return False

    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_str))
    return hmac.compare_digest(actual, expected)
