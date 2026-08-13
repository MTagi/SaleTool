"""Implementation SQLite của UserRepository/SearchRunRepository — mặc định
hiện tại, 1 file, không cần server DB riêng."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from saletool.db.base import SearchRunRepository, UserRepository
from saletool.models import CompanyResult, SearchCriteria, SearchRunDetail, SearchRunSummary


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
        created_at = datetime.now(timezone.utc).isoformat()
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
                ORDER BY created_at DESC
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
                ORDER BY created_at DESC
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
