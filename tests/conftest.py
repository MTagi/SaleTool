"""Shared fixtures and helpers for API tests.

Seven test files need the same three things: a temporary SQLite database, two
accounts for checking access separation, and a way to get an Authorization
header. Previously each file duplicated all three, so setup changes had to be
made in seven places.
"""

from __future__ import annotations

import time

import pytest

from saletool.db.sqlite_repo import SQLiteUserRepository
from saletool.security import hash_password

# Two accounts: `alice` owns data, and `bob` verifies that users cannot read one
# another's history or jobs.
ALICE = ("alice", "s3cret-pass")
BOB = ("bob", "another-pass")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Temporary SQLite database and environment, with two accounts ready."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(path))
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "0" * 64)

    users = SQLiteUserRepository(path)
    for username, password in (ALICE, BOB):
        users.create_user(username, hash_password(password))

    return path


def auth(client, username: str = ALICE[0], password: str = ALICE[1]) -> dict:
    """Authorization header for an existing account."""
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def wait_for_job(client, headers: dict, url: str, timeout: float = 15.0) -> dict:
    """Poll a background job until it finishes and return its final state.

    The job runs as an asyncio task in TestClient's event loop, so there is no
    handle to await; polling is the only option.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(url, headers=headers).json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job at {url} did not finish in {timeout}s")


class StubProvider:
    """Fake provider for route tests.

    Apollo is the only product provider, but `/api/search` tests check the
    **route**, not Apollo (ApolloProvider has separate tests with HTTP-level
    mocks). This stub replaces the old MockProvider but exists only in tests.
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
def data_source_key(db_path):
    """Preconfigure the data source API key.

    Since the key moved from the form to Settings, every `/api/search` test needs
    this setup; otherwise the route returns 400 "No API key configured".
    """
    from saletool.db.factory import get_settings_repository

    repo = get_settings_repository()
    settings = repo.get_settings()
    settings.data_source.api_key = "test-key"
    repo.save_settings(settings, updated_by="alice")
    return settings.data_source


@pytest.fixture
def stub_provider(monkeypatch, data_source_key):
    """Replace the provider created by the route with StubProvider.

    Also set `data_source_key` because `/api/search` now reads the key from
    Settings; without it, the route returns 400 before reaching the provider.
    """
    monkeypatch.setattr(
        "saletool.api.routes.search.get_provider", lambda name, **kwargs: StubProvider()
    )
