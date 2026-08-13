"""Implementation MongoDB của UserRepository — sẵn sàng để chuyển sang khi cần
scale, chưa bật mặc định. Cần cài thêm `pymongo` (không nằm trong
requirements.txt gốc, xem requirements-mongo.txt) và một MongoDB server.

`client` cho phép inject 1 client tương thích pymongo (vd: mongomock trong
test) thay vì luôn kết nối MongoDB thật.
"""

from __future__ import annotations

from typing import Any

from saletool.db.base import UserRepository


class MongoUserRepository(UserRepository):
    def __init__(self, uri: str, db_name: str, client: Any = None):
        if client is None:
            try:
                from pymongo import MongoClient
            except ImportError as exc:
                raise RuntimeError(
                    "Cần cài đặt 'pymongo' để dùng MongoDB backend: pip install pymongo "
                    "(hoặc pip install -r requirements-mongo.txt)"
                ) from exc
            client = MongoClient(uri)

        self._collection = client[db_name]["users"]
        self._collection.create_index("username", unique=True)

    def create_user(self, username: str, password_hash: str) -> None:
        username = username.strip()
        if not username or not password_hash:
            raise ValueError("Tên đăng nhập và mật khẩu không được để trống.")

        from pymongo.errors import DuplicateKeyError

        try:
            self._collection.insert_one({"username": username, "password_hash": password_hash})
        except DuplicateKeyError as exc:
            raise ValueError(f"Tài khoản '{username}' đã tồn tại.") from exc

    def get_password_hash(self, username: str) -> str | None:
        doc = self._collection.find_one({"username": username.strip()})
        return doc["password_hash"] if doc else None
