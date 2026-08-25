"""Test /api/match — chạy job thật ở nền, chỉ thay lớp gọi LLM bằng bản giả."""


import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import (
    SQLiteSearchRunRepository,
    SQLiteSettingsRepository,
)
from saletool.models import AppSettings, Company, CompanyResult, SearchCriteria
from tests.conftest import auth, wait_for_job


def _scored_response(scores: dict[str, int]):
    """Bản giả của lớp gọi LLM: trả điểm cố định theo nhãn dịch vụ."""

    async def fake_request_json(settings, payload, timeout=None):
        return {
            "summary": "Looks workable.",
            "signals": ["public tender history"],
            "concerns": [],
            "service_fits": [
                {"service_ref": ref, "score": score, "rationale": "test"}
                for ref, score in scores.items()
            ],
        }

    return fake_request_json


@pytest.fixture
def configured(db_path):
    """Matching cần LLM key, nếu không route sẽ chặn ngay từ đầu."""
    settings = AppSettings()
    settings.llm.api_key = "sk-or-test"
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")
    return db_path


@pytest.fixture
def client(configured, monkeypatch):
    monkeypatch.setattr(
        "saletool.matching.llm.request_json", _scored_response({"S1": 40, "S2": 85})
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def run_id(configured):
    """1 lần search đã lưu, 2 công ty."""
    return (
        SQLiteSearchRunRepository(configured)
        .save_run(
            username="alice",
            provider="mock",
            criteria=SearchCriteria(keywords=["fintech"]),
            results=[
                CompanyResult(company=Company(name="Acme Fintech", domain="acme.vn")),
                CompanyResult(company=Company(name="Beta Logistics", domain="beta.vn")),
            ],
        )
        .id
    )


def _services(client, headers, names=("ERP", "Audit")) -> list[str]:
    return [
        client.post(
            "/api/catalog", headers=headers, json={"name": name, "description": f"{name} work"}
        ).json()["id"]
        for name in names
    ]


def test_match_requires_auth(client, run_id):
    resp = client.post("/api/match", json={"run_id": run_id, "service_ids": ["x"]})
    assert resp.status_code == 401


def test_rejects_empty_service_selection(client, run_id):
    resp = client.post(
        "/api/match", headers=auth(client), json={"run_id": run_id, "service_ids": []}
    )
    assert resp.status_code == 422


def test_rejects_unknown_run(client):
    headers = auth(client)
    resp = client.post(
        "/api/match",
        headers=headers,
        json={"run_id": "not-a-run", "service_ids": _services(client, headers)},
    )
    assert resp.status_code == 404


def test_rejects_unknown_service(client, run_id):
    resp = client.post(
        "/api/match",
        headers=auth(client),
        json={"run_id": run_id, "service_ids": ["ghost-service"]},
    )
    assert resp.status_code == 400
    assert "no longer exists" in resp.json()["detail"]


def test_rejects_another_users_run(client, run_id):
    """run_id của alice không được map bằng token của bob."""
    bob = auth(client, "bob", "another-pass")
    resp = client.post(
        "/api/match",
        headers=bob,
        json={"run_id": run_id, "service_ids": _services(client, bob)},
    )
    assert resp.status_code == 404


def test_returns_a_job_immediately(client, run_id):
    headers = auth(client)
    resp = client.post(
        "/api/match",
        headers=headers,
        json={"run_id": run_id, "service_ids": _services(client, headers)},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"]
    assert body["total"] == 2
    assert body["status"] in ("pending", "running")


def test_job_ranks_every_company_in_the_run(client, run_id):
    headers = auth(client)
    job_id = client.post(
        "/api/match",
        headers=headers,
        json={"run_id": run_id, "service_ids": _services(client, headers)},
    ).json()["job_id"]

    final = wait_for_job(client, headers, f"/api/match/jobs/{job_id}")

    assert final["status"] == "completed"
    assert final["completed"] == 2
    assert final["failed"] == 0
    assert len(final["results"]) == 2
    assert [m["rank"] for m in final["results"]] == [1, 2]
    # Điểm tổng = dịch vụ khớp nhất (S2 = 85 trong bản giả).
    assert final["results"][0]["overall_score"] == 85
    assert final["results"][0]["best_service_name"] == "Audit"


def test_job_snapshots_the_services_it_ran_with(client, run_id):
    """Xoá dịch vụ khỏi catalog không được làm hỏng kết quả đã chạy."""
    headers = auth(client)
    service_ids = _services(client, headers)
    job_id = client.post(
        "/api/match", headers=headers, json={"run_id": run_id, "service_ids": service_ids}
    ).json()["job_id"]
    wait_for_job(client, headers, f"/api/match/jobs/{job_id}")

    for service_id in service_ids:
        client.delete(f"/api/catalog/{service_id}", headers=headers)

    job = client.get(f"/api/match/jobs/{job_id}", headers=headers).json()
    assert [s["name"] for s in job["services"]] == ["ERP", "Audit"]
    assert job["results"][0]["best_service_name"] == "Audit"


def test_objective_is_stored_on_the_job(client, run_id):
    headers = auth(client)
    job_id = client.post(
        "/api/match",
        headers=headers,
        json={
            "run_id": run_id,
            "service_ids": _services(client, headers),
            "objective": "  prefer fast decision makers  ",
        },
    ).json()["job_id"]

    job = client.get(f"/api/match/jobs/{job_id}", headers=headers).json()
    assert job["objective"] == "prefer fast decision makers"


def test_job_is_scoped_to_its_owner(client, run_id):
    headers = auth(client)
    job_id = client.post(
        "/api/match",
        headers=headers,
        json={"run_id": run_id, "service_ids": _services(client, headers)},
    ).json()["job_id"]

    bob = auth(client, "bob", "another-pass")
    assert client.get(f"/api/match/jobs/{job_id}", headers=bob).status_code == 404


def test_unknown_job_is_404(client):
    assert client.get("/api/match/jobs/nope", headers=auth(client)).status_code == 404


def test_jobs_list_shows_history(client, run_id):
    headers = auth(client)
    client.post(
        "/api/match",
        headers=headers,
        json={"run_id": run_id, "service_ids": _services(client, headers)},
    )

    jobs = client.get("/api/match/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["run_id"] == run_id


def test_llm_failures_are_counted_not_fatal(client, run_id, monkeypatch):
    from saletool.llm_api import LLMError

    async def always_fails(*args, **kwargs):
        raise LLMError("provider is down")

    monkeypatch.setattr("saletool.matching.llm.request_json", always_fails)

    headers = auth(client)
    job_id = client.post(
        "/api/match",
        headers=headers,
        json={"run_id": run_id, "service_ids": _services(client, headers)},
    ).json()["job_id"]

    final = wait_for_job(client, headers, f"/api/match/jobs/{job_id}")

    # Job vẫn phải hoàn tất và trả về đủ công ty, kèm lý do lỗi cho từng cái.
    assert final["status"] == "completed"
    assert final["failed"] == 2
    assert len(final["results"]) == 2
    assert all(m["error"] for m in final["results"])


def test_rejects_matching_without_an_llm_key(db_path, run_id, monkeypatch):
    settings = AppSettings()
    settings.llm.api_key = None
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    with TestClient(app) as client:
        headers = auth(client)
        resp = client.post(
            "/api/match",
            headers=headers,
            json={"run_id": run_id, "service_ids": _services(client, headers)},
        )

    assert resp.status_code == 400
    assert "LLM API key" in resp.json()["detail"]


def test_rejects_a_run_with_no_companies(configured):
    empty_run = (
        SQLiteSearchRunRepository(configured)
        .save_run(username="alice", provider="mock", criteria=SearchCriteria(), results=[])
        .id
    )

    with TestClient(app) as client:
        headers = auth(client)
        resp = client.post(
            "/api/match",
            headers=headers,
            json={"run_id": empty_run, "service_ids": _services(client, headers)},
        )

    assert resp.status_code == 400
    assert "no companies" in resp.json()["detail"]
