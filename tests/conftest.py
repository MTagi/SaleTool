"""Fixture và helper dùng chung cho các test API.

Bảy file test đều cần đúng ba thứ: một DB SQLite tạm, hai tài khoản để kiểm tra
phân tách quyền, và một cách lấy header Authorization. Trước đây mỗi file tự
chép lại cả ba — sửa cách khởi tạo là phải sửa bảy chỗ.
"""

from __future__ import annotations

import time

import pytest

from saletool.db.sqlite_repo import SQLiteUserRepository
from saletool.security import hash_password

# Hai tài khoản: `alice` sở hữu dữ liệu, `bob` dùng để kiểm tra rằng không ai
# đọc được lịch sử/job của người khác.
ALICE = ("alice", "s3cret-pass")
BOB = ("bob", "another-pass")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """DB SQLite tạm + biến môi trường, kèm sẵn hai tài khoản."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(path))
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "0" * 64)

    users = SQLiteUserRepository(path)
    for username, password in (ALICE, BOB):
        users.create_user(username, hash_password(password))

    return path


def auth(client, username: str = ALICE[0], password: str = ALICE[1]) -> dict:
    """Header Authorization cho 1 tài khoản đã có sẵn."""
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def wait_for_job(client, headers: dict, url: str, timeout: float = 15.0) -> dict:
    """Poll 1 job nền tới khi kết thúc, trả về trạng thái cuối.

    Job chạy bằng asyncio task trong event loop của TestClient nên không có
    handle nào để await — poll là cách duy nhất.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(url, headers=headers).json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job at {url} did not finish in {timeout}s")


class StubProvider:
    """Provider giả cho test route.

    Sản phẩm chỉ còn Apollo, nhưng test của `/api/search` kiểm tra **route** chứ
    không kiểm tra Apollo (ApolloProvider có bộ test riêng, mock ở tầng HTTP).
    Stub này giữ vai trò cũ của MockProvider nhưng nằm trong test, không nằm
    trong sản phẩm.
    """

    name = "stub"

    def search_companies(self, criteria):
        from saletool.models import Company

        keyword = criteria.keywords[0] if criteria.keywords else "Demo"
        return [
            Company(
                name=f"{keyword} Company {i}",
                linkedin_url=f"https://www.linkedin.com/company/{keyword.lower()}-company-{i}",
                domain=f"{keyword.lower()}company{i}.example.com",
                industry=criteria.industries[0] if criteria.industries else "Technology",
                location=criteria.locations[0] if criteria.locations else "Vietnam",
                employee_count=100 * i,
                provider_id=f"stub-org-{i}",
            )
            for i in range(1, criteria.max_companies + 1)
        ]

    def search_contacts(self, company, criteria):
        from saletool.models import Contact

        levels = criteria.seniority_levels or ["c_suite"]
        return [
            Contact(
                full_name=f"Contact {i} of {company.name}",
                title=criteria.target_titles[0] if criteria.target_titles else "CEO",
                seniority=levels[(i - 1) % len(levels)],
                linkedin_url=f"{company.linkedin_url}/employee-{i}",
                email=f"contact{i}@{company.domain}",
                company_name=company.name,
            )
            for i in range(1, criteria.max_contacts_per_company + 1)
        ]


@pytest.fixture
def stub_provider(monkeypatch):
    """Thay nhà cung cấp mà route dựng ra bằng StubProvider."""
    monkeypatch.setattr(
        "saletool.api.routes.search.get_provider", lambda name, **kwargs: StubProvider()
    )
