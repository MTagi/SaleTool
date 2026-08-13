"""Implementation SQLite của UserRepository — mặc định hiện tại, 1 file, không
cần server DB riêng."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from saletool.db.base import UserRepository


class SQLiteUserRepository(UserRepository):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
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

    def create_user(self, username: str, password_hash: str) -> None:
        username = username.strip()
        if not username or not password_hash:
            raise ValueError("Tên đăng nhập và mật khẩu không được để trống.")

        with sqlite3.connect(self.path) as conn:
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Tài khoản '{username}' đã tồn tại.") from exc

    def get_password_hash(self, username: str) -> str | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE username = ?", (username.strip(),)
            ).fetchone()
        return row[0] if row else None
