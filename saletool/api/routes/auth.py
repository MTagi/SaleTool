"""/api/auth/* — đăng nhập, thông tin user hiện tại."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from saletool.api.auth import authenticate, create_access_token
from saletool.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if not authenticate(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tên đăng nhập hoặc mật khẩu.",
        )
    token = create_access_token(payload.username.strip())
    return LoginResponse(access_token=token, username=payload.username.strip())


@router.get("/me")
def me(user: str = Depends(get_current_user)) -> dict:
    return {"username": user}
