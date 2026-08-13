"""Lưu trữ tài khoản đăng nhập cho web UI (SQLite, 1 file, không cần server DB riêng).

Không có API tự đăng ký công khai — tài khoản được tạo bởi người vận hành qua
CLI (`saletool web create-user`), phù hợp với một tool nội bộ dùng trong nhóm nhỏ.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from saletool.web.auth import hash_password, verify_password

DEFAULT_DB_PATH = Path(os.environ.get("SALETOOL_DB_PATH", "saletool.db"))


def _resolve_path(path: Path | None) -> Path:
    """Path được truyền vào thắng; nếu không, đọc biến môi trường tại thời điểm
    gọi (không phải tại thời điểm import module) để dễ cấu hình/test."""

    if path is not None:
        return path
    return Path(os.environ.get("SALETOOL_DB_PATH", "saletool.db"))


def init_db(path: Path | None = None) -> None:
    path = _resolve_path(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_user(username: str, password: str, path: Path | None = None) -> None:
    username = username.strip()
    if not username or not password:
        raise ValueError("Tên đăng nhập và mật khẩu không được để trống.")

    path = _resolve_path(path)
    init_db(path)
    with sqlite3.connect(path) as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Tài khoản '{username}' đã tồn tại.") from exc


def verify_user(username: str, password: str, path: Path | None = None) -> bool:
    path = _resolve_path(path)
    init_db(path)
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()

    if not row:
        return False
    return verify_password(password, row[0])
