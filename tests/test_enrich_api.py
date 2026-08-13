import time

import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import SQLiteSettingsRepository, SQLiteUserRepository
from saletool.models import AppSettings
from saletool.security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "enrich_test.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(db_path))
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "d" * 64)

    repo = SQLiteUserRepository(db_path)
    repo.create_user("alice", hash_password("s3cret-pass"))
    repo.create_user("bob", hash_password("another-pass"))

    # Cấu hình tối thiểu chạy được: chỉ website + tầng 0, không LLM, không search.
    settings = AppSettings()
    settings.enrichment.use_llm = False
    settings.enrichment.request_delay_seconds = 0
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    with TestClient(app) as c:
        yield c


def _auth(client, username="alice", password="s3cret-pass") -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _wait_for_job(client, headers, job_id, timeout=15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/enrich/jobs/{job_id}", headers=headers).json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.1)
    raise AssertionError(f"Job {job_id} did not finish in {timeout}s")


def test_enrich_requires_auth(client):
    resp = client.post("/api/enrich", json={"targets": [{"company_name": "Acme"}]})
    assert resp.status_code == 401


def test_enrich_rejects_empty_targets(client):
    resp = client.post("/api/enrich", headers=_auth(client), json={"targets": []})
    assert resp.status_code == 422


def test_enrich_rejects_target_without_name_or_domain(client):
    resp = client.post(
        "/api/enrich", headers=_auth(client), json={"targets": [{"company_name": "   "}]}
    )
    assert resp.status_code == 400


def test_enrich_returns_job_immediately(client):
    resp = client.post(
        "/api/enrich",
        headers=_auth(client),
        json={"targets": [{"company_name": "Nonexistent Co", "domain": "does-not-resolve.invalid"}]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"]
    assert body["total"] == 1
    assert body["status"] in ("pending", "running")


def test_job_runs_to_completion_and_is_pollable(client):
    headers = _auth(client)
    job_id = client.post(
        "/api/enrich",
        headers=headers,
        json={"targets": [{"company_name": "Nonexistent Co", "domain": "does-not-resolve.invalid"}]},
    ).json()["job_id"]

    final = _wait_for_job(client, headers, job_id)

    # Domain không tồn tại -> vẫn phải hoàn tất job (không treo, không 500).
    assert final["status"] == "completed"
    assert final["total"] == 1
    assert len(final["results"]) == 1
    assert final["results"][0]["company_name"] == "Nonexistent Co"


def test_job_is_scoped_to_owner(client):
    alice_headers = _auth(client)
    job_id = client.post(
        "/api/enrich",
        headers=alice_headers,
        json={"targets": [{"company_name": "Acme", "domain": "does-not-resolve.invalid"}]},
    ).json()["job_id"]

    bob_headers = _auth(client, "bob", "another-pass")
    assert client.get(f"/api/enrich/jobs/{job_id}", headers=bob_headers).status_code == 404


def test_unknown_job_returns_404(client):
    assert client.get("/api/enrich/jobs/not-a-real-id", headers=_auth(client)).status_code == 404


def test_jobs_list_shows_history(client):
    headers = _auth(client)
    client.post(
        "/api/enrich",
        headers=headers,
        json={"targets": [{"company_name": "A", "domain": "does-not-resolve.invalid"}]},
    )

    jobs = client.get("/api/enrich/jobs", headers=headers).json()
    assert len(jobs) >= 1
    assert jobs[0]["username"] == "alice"


def test_rejects_when_no_source_enabled(client, tmp_path, monkeypatch):
    settings = AppSettings()
    settings.enrichment.use_company_website = False
    settings.enrichment.use_web_search = False
    settings.enrichment.use_llm = False
    SQLiteSettingsRepository(tmp_path / "enrich_test.db").save_settings(settings, updated_by="alice")

    resp = client.post(
        "/api/enrich", headers=_auth(client), json={"targets": [{"company_name": "Acme"}]}
    )

    assert resp.status_code == 400
    assert "enrichment source" in resp.json()["detail"]
