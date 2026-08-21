"""Test /api/messages — chạy job thật ở nền, chỉ thay lớp gọi LLM bằng bản giả."""

import time

import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import (
    SQLiteSearchRunRepository,
    SQLiteSettingsRepository,
    SQLiteUserRepository,
)
from saletool.models import (
    AppSettings,
    Company,
    CompanyResult,
    Contact,
    SearchCriteria,
    SenderProfile,
)
from saletool.security import hash_password

GOOD_BODY = "Hi Lan, I noticed Acme still closes the books by hand. Worth a quick look?"


async def _fake_write(settings, payload, timeout=None):
    return {
        "subject": "quick question about your close",
        "body": GOOD_BODY,
        "personalization_used": ["closes the books by hand"],
    }


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "messages_test.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(path))
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "a" * 64)

    users = SQLiteUserRepository(path)
    users.create_user("alice", hash_password("s3cret-pass"))
    users.create_user("bob", hash_password("another-pass"))

    settings = AppSettings()
    settings.llm.api_key = "sk-or-test"
    settings.sender = SenderProfile(full_name="Tran Van A", company_name="ABIM")
    SQLiteSettingsRepository(path).save_settings(settings, updated_by="alice")

    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr("saletool.messaging.llm.request_json", _fake_write)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def run_id(db_path):
    """1 lần search đã lưu: 1 công ty 3 contact, 1 công ty 1 contact.

    Ba người ở cùng công ty là để chạm ngưỡng cảnh báo (khuyến nghị 1-2)."""
    return (
        SQLiteSearchRunRepository(db_path)
        .save_run(
            username="alice",
            provider="mock",
            criteria=SearchCriteria(keywords=["manufacturing"]),
            results=[
                CompanyResult(
                    company=Company(name="Acme Manufacturing", domain="acme.vn"),
                    contacts=[
                        Contact(full_name="Tran Thi Lan", title="CFO", email="lan@acme.vn"),
                        Contact(full_name="Nguyen Van Minh", title="Head of Ops"),
                        Contact(full_name="Le Hoang Nam", title="IT Manager"),
                    ],
                ),
                CompanyResult(
                    company=Company(name="Beta Logistics"),
                    contacts=[Contact(full_name="Pham Quoc Anh", title="CEO")],
                ),
            ],
        )
        .id
    )


def _auth(client, username="alice", password="s3cret-pass") -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _payload(run_id, **overrides) -> dict:
    payload = {
        "run_id": run_id,
        "targets": [{"company_name": "Acme Manufacturing", "contact_name": "Tran Thi Lan"}],
        "channel": "email",
        "tone": "direct",
        "language": "en",
    }
    payload.update(overrides)
    return payload


def _wait_for_job(client, headers, job_id, timeout=15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/messages/jobs/{job_id}", headers=headers).json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish in {timeout}s")


def test_requires_auth(client, run_id):
    assert client.post("/api/messages", json=_payload(run_id)).status_code == 401
    assert client.get("/api/messages/options").status_code == 401


def test_options_expose_the_real_channel_limits(client):
    """UI hiển thị giới hạn lấy từ backend, không chép cứng — 1 chỗ đúng duy nhất."""
    body = client.get("/api/messages/options", headers=_auth(client)).json()

    connection = next(c for c in body["channels"] if c["id"] == "linkedin_connection")
    assert connection["max_body_chars"] == 300
    assert connection["has_subject"] is False

    inmail = next(c for c in body["channels"] if c["id"] == "linkedin_inmail")
    assert inmail["max_subject_chars"] == 200
    assert inmail["max_body_chars"] == 1900

    assert "vi" in body["languages"]
    assert body["recommended_contacts_per_company"] == 2


def test_empty_target_list_is_rejected(client, run_id):
    resp = client.post("/api/messages", headers=_auth(client), json=_payload(run_id, targets=[]))
    assert resp.status_code == 422


def test_unknown_channel_is_rejected(client, run_id):
    resp = client.post(
        "/api/messages", headers=_auth(client), json=_payload(run_id, channel="carrier-pigeon")
    )
    assert resp.status_code == 400


def test_unknown_language_is_rejected(client, run_id):
    resp = client.post("/api/messages", headers=_auth(client), json=_payload(run_id, language="fr"))
    assert resp.status_code == 400


def test_another_users_run_is_not_reachable(client, run_id):
    bob = _auth(client, "bob", "another-pass")
    resp = client.post("/api/messages", headers=bob, json=_payload(run_id))
    assert resp.status_code == 404


def test_job_writes_a_message_for_the_contact(client, run_id):
    headers = _auth(client)
    job_id = client.post("/api/messages", headers=headers, json=_payload(run_id)).json()["job_id"]

    final = _wait_for_job(client, headers, job_id)

    assert final["status"] == "completed"
    assert final["completed"] == 1
    assert final["failed"] == 0

    message = final["results"][0]
    assert message["contact_name"] == "Tran Thi Lan"
    assert message["contact_title"] == "CFO"
    assert message["contact_email"] == "lan@acme.vn"  # lấy từ run, không do LLM bịa
    assert message["body"] == GOOD_BODY
    assert message["subject"]
    assert message["warnings"] == []


def test_a_contact_not_in_the_run_is_reported_not_invented(client, run_id):
    """Client không được tự thêm người ngoài dữ liệu đã lưu."""
    headers = _auth(client)
    job_id = client.post(
        "/api/messages",
        headers=headers,
        json=_payload(
            run_id,
            targets=[{"company_name": "Acme Manufacturing", "contact_name": "Ghost Person"}],
        ),
    ).json()["job_id"]

    final = _wait_for_job(client, headers, job_id)

    assert final["failed"] == 1
    assert "not in the selected search run" in final["results"][0]["error"]


def test_too_many_contacts_at_one_company_raises_a_notice(client, run_id):
    """Apollo đo: rải nhiều người cùng 1 công ty làm tụt tỉ lệ trả lời."""
    headers = _auth(client)
    resp = client.post(
        "/api/messages",
        headers=headers,
        json=_payload(
            run_id,
            targets=[
                {"company_name": "Acme Manufacturing", "contact_name": "Tran Thi Lan"},
                {"company_name": "Acme Manufacturing", "contact_name": "Nguyen Van Minh"},
                {"company_name": "Acme Manufacturing", "contact_name": "Le Hoang Nam"},
                {"company_name": "Beta Logistics", "contact_name": "Pham Quoc Anh"},
            ],
        ),
    )

    notices = resp.json()["notices"]
    assert any("reply rates" in n for n in notices)


def test_no_notice_at_exactly_two_contacts_per_company(client, run_id):
    """Hai người/công ty vẫn nằm trong khuyến nghị — cảnh báo ở đây là nhiễu."""
    headers = _auth(client)
    resp = client.post(
        "/api/messages",
        headers=headers,
        json=_payload(
            run_id,
            targets=[
                {"company_name": "Acme Manufacturing", "contact_name": "Tran Thi Lan"},
                {"company_name": "Acme Manufacturing", "contact_name": "Nguyen Van Minh"},
                {"company_name": "Beta Logistics", "contact_name": "Pham Quoc Anh"},
            ],
        ),
    )

    assert not any("reply rates" in n for n in resp.json()["notices"])


def test_missing_matching_run_is_called_out_up_front(client, run_id):
    resp = client.post("/api/messages", headers=_auth(client), json=_payload(run_id))
    assert any("No matching run" in n for n in resp.json()["notices"])


def test_job_is_scoped_to_its_owner(client, run_id):
    headers = _auth(client)
    job_id = client.post("/api/messages", headers=headers, json=_payload(run_id)).json()["job_id"]

    bob = _auth(client, "bob", "another-pass")
    assert client.get(f"/api/messages/jobs/{job_id}", headers=bob).status_code == 404


def test_unknown_job_is_404(client):
    assert client.get("/api/messages/jobs/nope", headers=_auth(client)).status_code == 404


def test_jobs_list_shows_history(client, run_id):
    headers = _auth(client)
    client.post("/api/messages", headers=headers, json=_payload(run_id))

    jobs = client.get("/api/messages/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["run_id"] == run_id
    assert jobs[0]["channel"] == "email"


def test_rejects_when_there_is_no_sender_profile(db_path, run_id, monkeypatch):
    """Không có người gửi thì LLM buộc phải bịa ra một người — chặn từ đầu."""
    monkeypatch.setattr("saletool.messaging.llm.request_json", _fake_write)

    settings = AppSettings()
    settings.llm.api_key = "sk-or-test"
    settings.sender = SenderProfile(full_name="", company_name="")
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    with TestClient(app) as client:
        resp = client.post("/api/messages", headers=_auth(client), json=_payload(run_id))

    assert resp.status_code == 400
    assert "Sender profile" in resp.json()["detail"]


def test_rejects_without_an_llm_key(db_path, run_id):
    settings = AppSettings()
    settings.llm.api_key = None
    settings.sender = SenderProfile(full_name="Tran Van A", company_name="ABIM")
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    with TestClient(app) as client:
        resp = client.post("/api/messages", headers=_auth(client), json=_payload(run_id))

    assert resp.status_code == 400
    assert "LLM API key" in resp.json()["detail"]


def test_llm_failure_is_counted_not_fatal(client, run_id, monkeypatch):
    from saletool.llm_api import LLMError

    async def always_fails(*args, **kwargs):
        raise LLMError("provider is down")

    monkeypatch.setattr("saletool.messaging.llm.request_json", always_fails)

    headers = _auth(client)
    job_id = client.post("/api/messages", headers=headers, json=_payload(run_id)).json()["job_id"]

    final = _wait_for_job(client, headers, job_id)

    assert final["status"] == "completed"
    assert final["failed"] == 1
    assert final["results"][0]["error"]
