"""Băm và xác thực mật khẩu (stdlib only — không phụ thuộc thư viện ngoài).

Dùng PBKDF2-HMAC-SHA256, không phải giải pháp mạnh nhất hiện có (bcrypt/argon2)
nhưng đủ tốt cho một tool nội bộ và tránh phụ thuộc vào extension biên dịch native.
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
