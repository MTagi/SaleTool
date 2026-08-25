"""Chọn implementation repository theo biến môi trường SALETOOL_DB_BACKEND.

Mặc định: sqlite. Đổi sang Mongo sau này chỉ cần set
SALETOOL_DB_BACKEND=mongo (+ SALETOOL_MONGO_URI, SALETOOL_MONGO_DB) mà không
phải sửa route hay logic auth/search/enrich nào.

Import module implementation được hoãn tới lúc gọi: `mongo_repo` cần pymongo,
một dependency tuỳ chọn, nên import ở đầu file sẽ làm hỏng cài đặt mặc định.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar

from saletool.db.base import (
    EnrichJobRepository,
    MatchJobRepository,
    MessageJobRepository,
    SearchRunRepository,
    ServiceRepository,
    SettingsRepository,
    UserRepository,
)

T = TypeVar("T")


def _backend() -> str:
    return os.environ.get("SALETOOL_DB_BACKEND", "sqlite").strip().lower()


def _sqlite_path() -> str:
    return os.environ.get("SALETOOL_DB_PATH", "saletool.db")


def _mongo_config() -> tuple[str, str]:
    uri = os.environ.get("SALETOOL_MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("SALETOOL_MONGO_DB", "saletool")
    return uri, db_name


def _select(sqlite_name: str, mongo_name: str) -> Callable[[], T]:
    """Dựng repository theo backend đang bật.

    Nhận **tên lớp** chứ không nhận lớp: tên lớp chỉ được tra cứu trong module
    tương ứng sau khi đã chọn backend, nên `pymongo` không bị import khi chạy
    SQLite.
    """
    backend = _backend()

    if backend == "sqlite":
        from saletool.db import sqlite_repo

        return getattr(sqlite_repo, sqlite_name)(_sqlite_path())

    if backend == "mongo":
        from saletool.db import mongo_repo

        return getattr(mongo_repo, mongo_name)(*_mongo_config())

    raise ValueError(f"Không hỗ trợ DB backend: '{backend}' (chỉ hỗ trợ 'sqlite' hoặc 'mongo')")


def get_user_repository() -> UserRepository:
    return _select("SQLiteUserRepository", "MongoUserRepository")


def get_search_run_repository() -> SearchRunRepository:
    return _select("SQLiteSearchRunRepository", "MongoSearchRunRepository")


def get_settings_repository() -> SettingsRepository:
    return _select("SQLiteSettingsRepository", "MongoSettingsRepository")


def get_service_repository() -> ServiceRepository:
    return _select("SQLiteServiceRepository", "MongoServiceRepository")


def get_enrich_job_repository() -> EnrichJobRepository:
    return _select("SQLiteEnrichJobRepository", "MongoEnrichJobRepository")


def get_match_job_repository() -> MatchJobRepository:
    return _select("SQLiteMatchJobRepository", "MongoMatchJobRepository")


def get_message_job_repository() -> MessageJobRepository:
    return _select("SQLiteMessageJobRepository", "MongoMessageJobRepository")
