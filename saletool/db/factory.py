"""Chọn implementation repository theo biến môi trường SALETOOL_DB_BACKEND.

Mặc định: sqlite. Đổi sang Mongo sau này chỉ cần set
SALETOOL_DB_BACKEND=mongo (+ SALETOOL_MONGO_URI, SALETOOL_MONGO_DB) mà không
phải sửa route hay logic auth/search/enrich nào.
"""

from __future__ import annotations

import os

from saletool.db.base import (
    EnrichJobRepository,
    SearchRunRepository,
    SettingsRepository,
    UserRepository,
)


def _backend() -> str:
    return os.environ.get("SALETOOL_DB_BACKEND", "sqlite").strip().lower()


def _sqlite_path() -> str:
    return os.environ.get("SALETOOL_DB_PATH", "saletool.db")


def _mongo_config() -> tuple[str, str]:
    uri = os.environ.get("SALETOOL_MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("SALETOOL_MONGO_DB", "saletool")
    return uri, db_name


def _unsupported(backend: str) -> ValueError:
    return ValueError(f"Không hỗ trợ DB backend: '{backend}' (chỉ hỗ trợ 'sqlite' hoặc 'mongo')")


def get_user_repository() -> UserRepository:
    backend = _backend()

    if backend == "sqlite":
        from saletool.db.sqlite_repo import SQLiteUserRepository

        return SQLiteUserRepository(_sqlite_path())

    if backend == "mongo":
        from saletool.db.mongo_repo import MongoUserRepository

        return MongoUserRepository(*_mongo_config())

    raise _unsupported(backend)


def get_search_run_repository() -> SearchRunRepository:
    backend = _backend()

    if backend == "sqlite":
        from saletool.db.sqlite_repo import SQLiteSearchRunRepository

        return SQLiteSearchRunRepository(_sqlite_path())

    if backend == "mongo":
        from saletool.db.mongo_repo import MongoSearchRunRepository

        return MongoSearchRunRepository(*_mongo_config())

    raise _unsupported(backend)


def get_settings_repository() -> SettingsRepository:
    backend = _backend()

    if backend == "sqlite":
        from saletool.db.sqlite_repo import SQLiteSettingsRepository

        return SQLiteSettingsRepository(_sqlite_path())

    if backend == "mongo":
        from saletool.db.mongo_repo import MongoSettingsRepository

        return MongoSettingsRepository(*_mongo_config())

    raise _unsupported(backend)


def get_enrich_job_repository() -> EnrichJobRepository:
    backend = _backend()

    if backend == "sqlite":
        from saletool.db.sqlite_repo import SQLiteEnrichJobRepository

        return SQLiteEnrichJobRepository(_sqlite_path())

    if backend == "mongo":
        from saletool.db.mongo_repo import MongoEnrichJobRepository

        return MongoEnrichJobRepository(*_mongo_config())

    raise _unsupported(backend)
