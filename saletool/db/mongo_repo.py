"""Implementation MongoDB của các repository — sẵn sàng để chuyển sang khi cần
scale, chưa bật mặc định. Cần cài thêm `pymongo` (không nằm trong
requirements.txt gốc, xem requirements-mongo.txt) và một MongoDB server.

`client` cho phép inject 1 client tương thích pymongo (vd: mongomock trong
test) thay vì luôn kết nối MongoDB thật.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar

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
            "Cần cài đặt 'pymongo' để dùng MongoDB backend: pip install pymongo "
            "(hoặc pip install -r requirements-mongo.txt)"
        ) from exc
    return MongoClient(uri)


class MongoUserRepository(UserRepository):
    def __init__(self, uri: str, db_name: str, client: Any = None):
        self._collection = _connect(client, uri)[db_name]["users"]
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
        created_at = datetime.now(timezone.utc).isoformat()
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
                {"results": 0},  # bỏ field results nặng khi chỉ cần liệt kê
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
    """Cấu hình lưu trong 1 document duy nhất (_id = "app") — phạm vi toàn hệ thống."""

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
        return settings

    def save_settings(self, settings: AppSettings, updated_by: str) -> AppSettings:
        updated_at = datetime.now(timezone.utc).isoformat()

        to_store = settings.model_copy(deep=True)
        to_store.llm.api_key = encrypt(to_store.llm.api_key)
        to_store.search.api_key = encrypt(to_store.search.api_key)
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
    """Phần thân dùng chung cho cả ba loại job — xem `_SQLiteJobRepository`.

    `_list_projection` bỏ các field nặng khi liệt kê; mỗi loại job có bộ field
    nặng riêng nên đó là chỗ duy nhất chúng khác nhau ngoài tên collection.
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
