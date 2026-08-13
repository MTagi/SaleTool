"""Chọn implementation UserRepository/SearchRunRepository theo biến môi
trường SALETOOL_DB_BACKEND.

Mặc định: sqlite. Đổi sang Mongo sau này chỉ cần set
SALETOOL_DB_BACKEND=mongo (+ SALETOOL_MONGO_URI, SALETOOL_MONGO_DB) mà không
phải sửa route hay logic auth/search nào.
"""

from __future__ import annotations

import os

from saletool.db.base import SearchRunRepository, UserRepository


def _backend() -> str:
    return os.environ.get("SALETOOL_DB_BACKEND", "sqlite").strip().lower()


def get_user_repository() -> UserRepository:
    backend = _backend()

    if backend == "sqlite":
        from saletool.db.sqlite_repo import SQLiteUserRepository

        path = os.environ.get("SALETOOL_DB_PATH", "saletool.db")
        return SQLiteUserRepository(path)

    if backend == "mongo":
        from saletool.db.mongo_repo import MongoUserRepository

        uri = os.environ.get("SALETOOL_MONGO_URI", "mongodb://localhost:27017")
        db_name = os.environ.get("SALETOOL_MONGO_DB", "saletool")
        return MongoUserRepository(uri, db_name)

    raise ValueError(f"Không hỗ trợ DB backend: '{backend}' (chỉ hỗ trợ 'sqlite' hoặc 'mongo')")


def get_search_run_repository() -> SearchRunRepository:
    backend = _backend()

    if backend == "sqlite":
        from saletool.db.sqlite_repo import SQLiteSearchRunRepository

        path = os.environ.get("SALETOOL_DB_PATH", "saletool.db")
        return SQLiteSearchRunRepository(path)

    if backend == "mongo":
        from saletool.db.mongo_repo import MongoSearchRunRepository

        uri = os.environ.get("SALETOOL_MONGO_URI", "mongodb://localhost:27017")
        db_name = os.environ.get("SALETOOL_MONGO_DB", "saletool")
        return MongoSearchRunRepository(uri, db_name)

    raise ValueError(f"Không hỗ trợ DB backend: '{backend}' (chỉ hỗ trợ 'sqlite' hoặc 'mongo')")
