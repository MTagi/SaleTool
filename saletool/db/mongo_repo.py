"""Implementation MongoDB của UserRepository/SearchRunRepository — sẵn sàng để
chuyển sang khi cần scale, chưa bật mặc định. Cần cài thêm `pymongo` (không
nằm trong requirements.txt gốc, xem requirements-mongo.txt) và một MongoDB
server.

`client` cho phép inject 1 client tương thích pymongo (vd: mongomock trong
test) thay vì luôn kết nối MongoDB thật.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from saletool.db.base import SearchRunRepository, UserRepository
from saletool.models import CompanyResult, SearchCriteria, SearchRunDetail, SearchRunSummary


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
