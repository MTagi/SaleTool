"""Implementation SQLite của các repository — mặc định hiện tại, 1 file, không
cần server DB riêng."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from saletool.crypto import decrypt, encrypt
from saletool.clock import now_iso
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

    def update_password_hash(self, username: str, password_hash: str) -> None:
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, username.strip()),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"User '{username}' not found.")


class SQLiteSearchRunRepository(SearchRunRepository):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_runs (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    criteria_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    total_companies INTEGER NOT NULL,
                    total_contacts INTEGER NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_search_runs_username ON search_runs(username)")

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

        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO search_runs
                    (id, username, created_at, provider, criteria_json, results_json,
                     total_companies, total_contacts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    username,
                    created_at,
                    provider,
                    criteria.model_dump_json(),
                    json.dumps([r.model_dump() for r in results]),
                    len(results),
                    total_contacts,
                ),
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
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, provider, criteria_json, total_companies, total_contacts
                FROM search_runs
                WHERE username = ?
                -- rowid là thứ tự chèn. Cần nó cho những dòng lưu TRƯỚC khi
                -- saletool/clock.py ra đời: chúng vẫn có created_at trùng nhau,
                -- và không có tiebreaker thì thứ tự do engine tự quyết.
                -- An toàn vì bảng này không bao giờ bị xoá dòng, nên SQLite
                -- không tái sử dụng rowid.
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (username, limit),
            ).fetchall()

        return [
            SearchRunSummary(
                id=row[0],
                username=username,
                created_at=row[1],
                provider=row[2],
                criteria=SearchCriteria.model_validate_json(row[3]),
                total_companies=row[4],
                total_contacts=row[5],
            )
            for row in rows
        ]

    def get_run(self, username: str, run_id: str) -> SearchRunDetail | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT id, created_at, provider, criteria_json, results_json,
                       total_companies, total_contacts
                FROM search_runs
                WHERE id = ? AND username = ?
                """,
                (run_id, username),
            ).fetchone()

        if not row:
            return None
        return self._row_to_detail(username, row)

    def get_latest_run(self, username: str) -> SearchRunDetail | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT id, created_at, provider, criteria_json, results_json,
                       total_companies, total_contacts
                FROM search_runs
                WHERE username = ?
                ORDER BY created_at DESC, rowid DESC   -- xem chú thích ở list_runs
                LIMIT 1
                """,
                (username,),
            ).fetchone()

        if not row:
            return None
        return self._row_to_detail(username, row)

    @staticmethod
    def _row_to_detail(username: str, row: tuple) -> SearchRunDetail:
        run_id, created_at, provider, criteria_json, results_json, total_companies, total_contacts = row
        return SearchRunDetail(
            id=run_id,
            username=username,
            created_at=created_at,
            provider=provider,
            criteria=SearchCriteria.model_validate_json(criteria_json),
            total_companies=total_companies,
            total_contacts=total_contacts,
            results=[CompanyResult.model_validate(r) for r in json.loads(results_json)],
        )


class SQLiteSettingsRepository(SettingsRepository):
    """Cấu hình lưu trong 1 dòng duy nhất (id = 1) — phạm vi toàn hệ thống."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    settings_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT
                )
                """
            )

    def get_settings(self) -> AppSettings:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT settings_json, updated_at, updated_by FROM app_settings WHERE id = 1"
            ).fetchone()

        if not row:
            return AppSettings()

        settings = AppSettings.model_validate_json(row[0])
        settings.updated_at = row[1]
        settings.updated_by = row[2]
        # API key nằm trong DB ở dạng đã mã hoá — giải ra cho tầng gọi dùng.
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

        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO app_settings (id, settings_json, updated_at, updated_by)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    settings_json = excluded.settings_json,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (to_store.model_dump_json(), updated_at, updated_by),
            )

        saved = settings.model_copy(deep=True)
        saved.updated_at = updated_at
        saved.updated_by = updated_by
        return saved


class SQLiteServiceRepository(ServiceRepository):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS services (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    service_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_services_name ON services(name)")

    def list_services(self, include_inactive: bool = True) -> list[Service]:
        query = "SELECT service_json FROM services"
        if not include_inactive:
            query += " WHERE active = 1"
        query += " ORDER BY name COLLATE NOCASE"

        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(query).fetchall()
        return [Service.model_validate_json(row[0]) for row in rows]

    def get_service(self, service_id: str) -> Service | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT service_json FROM services WHERE id = ?", (service_id,)
            ).fetchone()
        return Service.model_validate_json(row[0]) if row else None

    def create_service(self, payload: ServiceInput, updated_by: str) -> Service:
        now = datetime.now(timezone.utc).isoformat()
        service = Service(
            **payload.model_dump(),
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            updated_by=updated_by,
        )

        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO services (id, name, active, created_at, updated_at, service_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    service.id,
                    service.name,
                    int(service.active),
                    service.created_at,
                    service.updated_at,
                    service.model_dump_json(),
                ),
            )
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

        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                UPDATE services
                SET name = ?, active = ?, updated_at = ?, service_json = ?
                WHERE id = ?
                """,
                (
                    service.name,
                    int(service.active),
                    service.updated_at,
                    service.model_dump_json(),
                    service_id,
                ),
            )
        return service

    def delete_service(self, service_id: str) -> bool:
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
        return cursor.rowcount > 0


class _SQLiteJobRepository:
    """Phần thân dùng chung cho cả ba loại job.

    Ba bảng job chỉ khác nhau ở tên bảng và kiểu dữ liệu; toàn bộ JSON của job
    nằm trong một cột nên câu lệnh SQL giống hệt nhau. Lớp con chỉ khai báo
    `_table` và hai model.
    """

    _table: str
    _detail_model: type
    _summary_model: type

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    job_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self._table}_username "
                f"ON {self._table}(username, created_at DESC)"
            )

    def create_job(self, job) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                f"INSERT INTO {self._table} (id, username, status, created_at, job_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (job.id, job.username, job.status, job.created_at, job.model_dump_json()),
            )

    def update_job(self, job) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                f"UPDATE {self._table} SET status = ?, job_json = ? WHERE id = ? AND username = ?",
                (job.status, job.model_dump_json(), job.id, job.username),
            )

    def get_job(self, username: str, job_id: str):
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                f"SELECT job_json FROM {self._table} WHERE id = ? AND username = ?",
                (job_id, username),
            ).fetchone()
        return self._detail_model.model_validate_json(row[0]) if row else None

    def list_jobs(self, username: str, limit: int = 20) -> list:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                f"""
                SELECT job_json FROM {self._table}
                WHERE username = ?
                ORDER BY created_at DESC, rowid DESC   -- xem chú thích ở list_runs
                LIMIT ?
                """,
                (username, limit),
            ).fetchall()

        # Summary bỏ các field nặng (results/targets/services) khi chỉ cần liệt kê.
        return [
            self._summary_model.model_validate(
                self._detail_model.model_validate_json(row[0]).model_dump()
            )
            for row in rows
        ]


class SQLiteEnrichJobRepository(_SQLiteJobRepository, EnrichJobRepository):
    _table = "enrich_jobs"
    _detail_model = EnrichJobDetail
    _summary_model = EnrichJobSummary


class SQLiteMatchJobRepository(_SQLiteJobRepository, MatchJobRepository):
    _table = "match_jobs"
    _detail_model = MatchJobDetail
    _summary_model = MatchJobSummary


class SQLiteMessageJobRepository(_SQLiteJobRepository, MessageJobRepository):
    _table = "message_jobs"
    _detail_model = MessageJobDetail
    _summary_model = MessageJobSummary
