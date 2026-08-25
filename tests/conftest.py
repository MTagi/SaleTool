"""Fixture và helper dùng chung cho các test API.

Bảy file test đều cần đúng ba thứ: một DB SQLite tạm, hai tài khoản để kiểm tra
phân tách quyền, và một cách lấy header Authorization. Trước đây mỗi file tự
chép lại cả ba — sửa cách khởi tạo là phải sửa bảy chỗ.
"""

from __future__ import annotations

import time

import pytest

from saletool.db.sqlite_repo import SQLiteUserRepository
from saletool.security import hash_password

# Hai tài khoản: `alice` sở hữu dữ liệu, `bob` dùng để kiểm tra rằng không ai
# đọc được lịch sử/job của người khác.
ALICE = ("alice", "s3cret-pass")
BOB = ("bob", "another-pass")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """DB SQLite tạm + biến môi trường, kèm sẵn hai tài khoản."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(path))
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "0" * 64)

    users = SQLiteUserRepository(path)
    for username, password in (ALICE, BOB):
        users.create_user(username, hash_password(password))

    return path


def auth(client, username: str = ALICE[0], password: str = ALICE[1]) -> dict:
    """Header Authorization cho 1 tài khoản đã có sẵn."""
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def wait_for_job(client, headers: dict, url: str, timeout: float = 15.0) -> dict:
    """Poll 1 job nền tới khi kết thúc, trả về trạng thái cuối.

    Job chạy bằng asyncio task trong event loop của TestClient nên không có
    handle nào để await — poll là cách duy nhất.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(url, headers=headers).json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job at {url} did not finish in {timeout}s")
