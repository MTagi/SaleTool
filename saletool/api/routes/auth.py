"""/api/auth/* — login, current user info, change password."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from saletool.api.auth import authenticate, create_access_token
from saletool.api.deps import get_current_user
from saletool.db.factory import get_user_repository
from saletool.security import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if not authenticate(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )
    token = create_access_token(payload.username.strip())
    return LoginResponse(access_token=token, username=payload.username.strip())


@router.get("/me")
def me(user: str = Depends(get_current_user)) -> dict:
    return {"username": user}


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, user: str = Depends(get_current_user)) -> dict:
    repo = get_user_repository()
    current_hash = repo.get_password_hash(user)
    if not current_hash or not verify_password(payload.current_password, current_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters.",
        )

    repo.update_password_hash(user, hash_password(payload.new_password))
    return {"status": "ok"}
