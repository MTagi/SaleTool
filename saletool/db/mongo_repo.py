"""MongoDB repository implementation — available for future scaling, but not
enabled by default. Requires `pymongo` (not in the base requirements.txt; see
requirements-mongo.txt) and a MongoDB server.

`client` allows injection of a pymongo-compatible client (e.g. mongomock in
tests) instead of always connecting to a real MongoDB instance.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar

from saletool.clock import now_iso
from saletool.crypto import decrypt, encrypt
from saletool.db.base import (
    EnrichJobRepository,
    MatchJobRepository,
    MessageJobRepository,
    SearchRunRepository,
    ServiceRepository,
    SettingsRepository,
    UserRepository,
)
from saletool.models import (
    AppSettings,
    CompanyResult,
    EnrichJobDetail,
    EnrichJobSummary,
    MatchJobDetail,
    MatchJobSummary,
    MessageJobDetail,
    MessageJobSummary,
    SearchCriteria,
    SearchRunDetail,
    SearchRunSummary,
    Service,
    ServiceInput,
)


def _connect(client: Any, uri: str) -> Any:
    if client is not None:
        return client
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError(
            "Install 'pymongo' to use the MongoDB backend: pip install pymongo "
            "(or pip install -r requirements-mongo.txt)"
        ) from exc
    return MongoClient(uri)


class MongoUserRepository(UserRepository):
    def __init__(self, uri: str, db_name: str, client: Any = None):
        self._collection = _connect(client, uri)[db_name]["users"]
        self._collection.create_index("username", unique=True)

    def create_user(self, username: str, password_hash: str) -> None:
        username = username.strip()
        if not username or not password_hash:
            raise ValueError("Username and password cannot be empty.")

        from pymongo.errors import DuplicateKeyError

        try:
            self._collection.insert_one({"username": username, "password_hash": password_hash})
        except DuplicateKeyError as exc:
            raise ValueError(f"Account '{username}' already exists.") from exc

    def get_password_hash(self, username: str) -> str | None:
        doc = self._collection.find_one({"username": username.strip()})
        return doc["password_hash"] if doc else None

    def update_password_hash(self, username: str, password_hash: str) -> None:
        result = self._collection.update_one(
            {"username": username.strip()}, {"$set": {"password_hash": password_hash}}
        )
        if result.matched_count == 0:
            raise ValueError(f"User '{username}' not found.")


class MongoSearchRunRepository(SearchRunRepository):
    def __init__(self, uri: str, db_name: str, client: Any = None):
        self._collection = _connect(client, uri)[db_name]["search_runs"]
        self._collection.create_index([("username", 1), ("created_at", -1)])

    def save_run(
        self,
        username: str,
        provider: str,
        criteria: SearchCriteria,
        results: list[CompanyResult],
    ) -> SearchRunSummary:
        run_id = str(uuid.uuid4())
        created_at = now_iso()
        total_contacts = sum(len(r.contacts) for r in results)

        self._collection.insert_one(
            {
                "_id": run_id,
                "username": username,
                "created_at": created_at,
                "provider": provider,
                "criteria": criteria.model_dump(mode="json"),
                "results": [r.model_dump(mode="json") for r in results],
                "total_companies": len(results),
                "total_contacts": total_contacts,
            }
        )

        return SearchRunSummary(
            id=run_id,
            username=username,
            created_at=created_at,
            provider=provider,
            criteria=criteria,
            total_companies=len(results),
            total_contacts=total_contacts,
        )

    def list_runs(self, username: str, limit: int = 20) -> list[SearchRunSummary]:
        cursor = (
            self._collection.find(
                {"username": username},
                {"results": 0},  # Omit large results when only listing records.
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._doc_to_summary(doc) for doc in cursor]

    def get_run(self, username: str, run_id: str) -> SearchRunDetail | None:
        doc = self._collection.find_one({"_id": run_id, "username": username})
        return self._doc_to_detail(doc) if doc else None

    def get_latest_run(self, username: str) -> SearchRunDetail | None:
        doc = self._collection.find_one({"username": username}, sort=[("created_at", -1)])
        return self._doc_to_detail(doc) if doc else None

    def delete_run(self, username: str, run_id: str) -> bool:
        result = self._collection.delete_one({"_id": run_id, "username": username})
        return result.deleted_count > 0
    @staticmethod
    def _doc_to_summary(doc: dict) -> SearchRunSummary:
        return SearchRunSummary(
            id=doc["_id"],
            username=doc["username"],
            created_at=doc["created_at"],
            provider=doc["provider"],
            criteria=SearchCriteria.model_validate(doc["criteria"]),
            total_companies=doc["total_companies"],
            total_contacts=doc["total_contacts"],
        )

    @staticmethod
    def _doc_to_detail(doc: dict) -> SearchRunDetail:
        return SearchRunDetail(
            id=doc["_id"],
            username=doc["username"],
            created_at=doc["created_at"],
            provider=doc["provider"],
            criteria=SearchCriteria.model_validate(doc["criteria"]),
            total_companies=doc["total_companies"],
            total_contacts=doc["total_contacts"],
            results=[CompanyResult.model_validate(r) for r in doc["results"]],
        )


class MongoSettingsRepository(SettingsRepository):
    """Configuration stored in one document (_id = "app"), system-wide."""

    _DOC_ID = "app"

    def __init__(self, uri: str, db_name: str, client: Any = None):
        self._collection = _connect(client, uri)[db_name]["app_settings"]

    def get_settings(self) -> AppSettings:
        doc = self._collection.find_one({"_id": self._DOC_ID})
        if not doc:
            return AppSettings()

        payload = {k: v for k, v in doc.items() if k != "_id"}
        settings = AppSettings.model_validate(payload)
        settings.llm.api_key = decrypt(settings.llm.api_key)
        settings.search.api_key = decrypt(settings.search.api_key)
        settings.data_source.api_key = decrypt(settings.data_source.api_key)
        return settings

    def save_settings(self, settings: AppSettings, updated_by: str) -> AppSettings:
        updated_at = datetime.now(timezone.utc).isoformat()

        to_store = settings.model_copy(deep=True)
        to_store.llm.api_key = encrypt(to_store.llm.api_key)
        to_store.search.api_key = encrypt(to_store.search.api_key)
        to_store.data_source.api_key = encrypt(to_store.data_source.api_key)
        to_store.updated_at = updated_at
        to_store.updated_by = updated_by

        self._collection.replace_one(
            {"_id": self._DOC_ID},
            {"_id": self._DOC_ID, **to_store.model_dump(mode="json")},
            upsert=True,
        )

        saved = settings.model_copy(deep=True)
        saved.updated_at = updated_at
        saved.updated_by = updated_by
        return saved


class MongoServiceRepository(ServiceRepository):
    def __init__(self, uri: str, db_name: str, client: Any = None):
        self._collection = _connect(client, uri)[db_name]["services"]
        self._collection.create_index("name")

    def list_services(self, include_inactive: bool = True) -> list[Service]:
        query = {} if include_inactive else {"active": True}
        cursor = self._collection.find(query).sort("name", 1)
        return [self._doc_to_service(doc) for doc in cursor]

    def get_service(self, service_id: str) -> Service | None:
        doc = self._collection.find_one({"_id": service_id})
        return self._doc_to_service(doc) if doc else None

    def create_service(self, payload: ServiceInput, updated_by: str) -> Service:
        now = datetime.now(timezone.utc).isoformat()
        service = Service(
            **payload.model_dump(),
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            updated_by=updated_by,
        )

        doc = service.model_dump(mode="json")
        doc["_id"] = doc.pop("id")
        self._collection.insert_one(doc)
        return service

    def update_service(self, service_id: str, payload: ServiceInput, updated_by: str) -> Service:
        existing = self.get_service(service_id)
        if not existing:
            raise ValueError(f"Service '{service_id}' not found.")

        service = Service(
            **payload.model_dump(),
            id=existing.id,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
            updated_by=updated_by,
        )

        doc = service.model_dump(mode="json")
        doc.pop("id", None)
        self._collection.update_one({"_id": service_id}, {"$set": doc})
        return service

    def delete_service(self, service_id: str) -> bool:
        return self._collection.delete_one({"_id": service_id}).deleted_count > 0

    @staticmethod
    def _doc_to_service(doc: dict) -> Service:
        return Service.model_validate({**doc, "id": doc["_id"]})


class _MongoJobRepository:
    """Shared implementation for all three job types; see `_SQLiteJobRepository`.

    `_list_projection` omits large fields when listing. Each job type has its own
    large fields, which is their only difference besides collection name.
    """

    _collection_name: str
    _detail_model: type
    _summary_model: type
    _list_projection: ClassVar[dict]

    def __init__(self, uri: str, db_name: str, client: Any = None):
        self._collection = _connect(client, uri)[db_name][self._collection_name]
        self._collection.create_index([("username", 1), ("created_at", -1)])

    def create_job(self, job) -> None:
        doc = job.model_dump(mode="json")
        doc["_id"] = doc.pop("id")
        self._collection.insert_one(doc)

    def update_job(self, job) -> None:
        doc = job.model_dump(mode="json")
        doc.pop("id", None)
        self._collection.update_one({"_id": job.id, "username": job.username}, {"$set": doc})

    def get_job(self, username: str, job_id: str):
        doc = self._collection.find_one({"_id": job_id, "username": username})
        return self._detail_model.model_validate({**doc, "id": doc["_id"]}) if doc else None

    def fail_active_jobs(self, reason: str, finished_at: str) -> int:
        result = self._collection.update_many(
            {"status": {"$in": ["pending", "running"]}},
            {"$set": {"status": "failed", "error": reason,
                      "finished_at": finished_at, "current_target": None}},
        )
        return result.modified_count

    def list_for_run(self, username: str, run_id: str, include_unlinked: bool = False) -> list:
        query = {"username": username, "run_id": {"$in": [run_id, None]} if include_unlinked else run_id}
        cursor = self._collection.find(query).sort([("created_at", -1), ("_id", -1)])
        return [self._detail_model.model_validate({**doc, "id": doc["_id"]}) for doc in cursor]

    def delete_for_run(self, username: str, run_id: str) -> None:
        self._collection.delete_many({"username": username, "run_id": run_id})
    def list_jobs(self, username: str, limit: int = 20) -> list:
        cursor = (
            self._collection.find({"username": username}, self._list_projection)
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._summary_model.model_validate({**doc, "id": doc["_id"]}) for doc in cursor]


class MongoEnrichJobRepository(_MongoJobRepository, EnrichJobRepository):
    _collection_name = "enrich_jobs"
    _detail_model = EnrichJobDetail
    _summary_model = EnrichJobSummary
    _list_projection: ClassVar[dict] = {"results": 0, "targets": 0}


class MongoMatchJobRepository(_MongoJobRepository, MatchJobRepository):
    _collection_name = "match_jobs"
    _detail_model = MatchJobDetail
    _summary_model = MatchJobSummary
    _list_projection: ClassVar[dict] = {"results": 0, "services": 0}


class MongoMessageJobRepository(_MongoJobRepository, MessageJobRepository):
    _collection_name = "message_jobs"
    _detail_model = MessageJobDetail
    _summary_model = MessageJobSummary
    _list_projection: ClassVar[dict] = {"results": 0}
