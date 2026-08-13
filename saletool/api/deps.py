"""FastAPI dependencies dùng chung."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from saletool.api.auth import decode_access_token


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu access token (Authorization: Bearer <token>).",
        )

    token = authorization.split(" ", 1)[1].strip()
    username = decode_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn.",
        )
    return username
