"""Select a repository implementation using the SALETOOL_DB_BACKEND environment variable.

Default: sqlite. To switch to MongoDB, set SALETOOL_DB_BACKEND=mongo (plus
SALETOOL_MONGO_URI and SALETOOL_MONGO_DB); no route or auth/search/enrichment
logic needs to change.

Implementation modules are imported only when called: `mongo_repo` requires
pymongo, an optional dependency, so importing it at module load would break the
default installation.
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
    """Build a repository for the selected backend.

    Accept a **class name**, not a class: the class is looked up in the selected
    module, so `pymongo` is not imported when using SQLite.
    """
    backend = _backend()

    if backend == "sqlite":
        from saletool.db import sqlite_repo

        return getattr(sqlite_repo, sqlite_name)(_sqlite_path())

    if backend == "mongo":
        from saletool.db import mongo_repo

        return getattr(mongo_repo, mongo_name)(*_mongo_config())

    raise ValueError(f"Unsupported database backend: '{backend}' (supported: 'sqlite' or 'mongo')")


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
