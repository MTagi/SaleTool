import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import (
    SQLiteSearchRunRepository,
    SQLiteServiceRepository,
    SQLiteSettingsRepository,
)
from saletool.models import (
    AppSettings,
    Company,
    CompanyResult,
    Contact,
    SearchCriteria,
    SenderProfile,
    ServiceInput,
)
from tests.conftest import auth


@pytest.fixture
def client(db_path):
    with TestClient(app) as c:
        yield c


def test_status_requires_auth(client):
    assert client.get("/api/status").status_code == 401


def test_fresh_install_reports_nothing_configured(client):
    body = client.get("/api/status", headers=auth(client)).json()

    assert body["llm_configured"] is False
    assert body["sender_configured"] is False
    assert body["counts"] == {
        "services": 0,
        "active_services": 0,
        "runs": 0,
        "enrich_jobs": 0,
        "match_jobs": 0,
        "message_jobs": 0,
    }
    assert body["latest_run"] is None


def test_reports_llm_and_sender_once_configured(client, db_path):
    settings = AppSettings()
    settings.llm.api_key = "sk-test"
    settings.sender = SenderProfile(full_name="Tran Van A", company_name="ABIM")
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    body = client.get("/api/status", headers=auth(client)).json()

    assert body["llm_configured"] is True
    assert body["sender_configured"] is True


def test_a_half_filled_sender_profile_does_not_count(client, db_path):
    """Có tên mà không có công ty thì message vẫn không viết được — đừng báo xanh."""
    settings = AppSettings()
    settings.sender = SenderProfile(full_name="Tran Van A", company_name="   ")
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    body = client.get("/api/status", headers=auth(client)).json()

    assert body["sender_configured"] is False


def test_counts_active_services_separately(client, db_path):
    repo = SQLiteServiceRepository(db_path)
    repo.create_service(ServiceInput(name="Live one"), updated_by="alice")
    repo.create_service(ServiceInput(name="Retired", active=False), updated_by="alice")

    counts = client.get("/api/status", headers=auth(client)).json()["counts"]

    assert counts["services"] == 2
    assert counts["active_services"] == 1


def test_latest_run_is_reported_for_shortcuts(client, db_path):
    run = SQLiteSearchRunRepository(db_path).save_run(
        username="alice",
        provider="mock",
        criteria=SearchCriteria(keywords=["fintech"]),
        results=[
            CompanyResult(
                company=Company(name="Acme"), contacts=[Contact(full_name="Tran Thi Lan")]
            )
        ],
    )

    body = client.get("/api/status", headers=auth(client)).json()

    assert body["latest_run"]["id"] == run.id
    assert body["latest_run"]["total_companies"] == 1
    assert body["latest_run"]["total_contacts"] == 1
    assert body["counts"]["runs"] == 1


def test_run_counts_are_per_user_but_catalog_is_shared(client, db_path):
    """Lịch sử là của từng người; catalog là của công ty — status phải phản ánh đúng."""
    SQLiteServiceRepository(db_path).create_service(ServiceInput(name="ERP"), updated_by="alice")
    SQLiteSearchRunRepository(db_path).save_run(
        username="alice", provider="mock", criteria=SearchCriteria(), results=[]
    )

    bob = client.get("/api/status", headers=auth(client, "bob", "another-pass")).json()

    assert bob["counts"]["runs"] == 0
    assert bob["counts"]["services"] == 1
