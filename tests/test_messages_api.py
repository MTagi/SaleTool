"""Test /api/messages with a real background job and a fake LLM client."""


import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import (
    SQLiteMatchJobRepository,
    SQLiteSearchRunRepository,
    SQLiteSettingsRepository,
)
from saletool.models import (
    AppSettings,
    Company,
    CompanyResult,
    Contact,
    MatchJobDetail,
    SearchCriteria,
    SenderProfile,
)
from tests.conftest import auth, wait_for_job

GOOD_BODY = "Hi Lan, I noticed Acme still closes the books by hand. Worth a quick look?"


async def _fake_write(settings, payload, timeout=None):
    return {
        "subject": "quick question about your close",
        "body": GOOD_BODY,
        "personalization_used": ["closes the books by hand"],
    }


@pytest.fixture
def configured(db_path):
    """An LLM key and sender profile are both required for message generation."""
    settings = AppSettings()
    settings.llm.api_key = "sk-or-test"
    settings.sender = SenderProfile(full_name="Tran Van A", company_name="ABIM")
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")
    return db_path


@pytest.fixture
def client(configured, monkeypatch):
    monkeypatch.setattr("saletool.messaging.llm.request_json", _fake_write)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def run_id(configured):
    """One saved search run: one company with three contacts, one with one contact.

    Three contacts at one company trigger the warning (recommendation: 1–2)."""
    return (
        SQLiteSearchRunRepository(configured)
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


@pytest.mark.parametrize(
    ("owner", "same_run", "state", "expected"),
    [
        ("alice", True, "completed", 200),
        ("alice", False, "completed", 400),
        ("alice", True, "running", 400),
        ("bob", True, "completed", 404),
    ],
)
def test_message_matching_context_belongs_to_selected_search(
    client, configured, run_id, monkeypatch, owner, same_run, state, expected
):
    monkeypatch.setattr("saletool.api.routes.messages.jobs.start_message_job", lambda job: None)
    SQLiteMatchJobRepository(configured).create_job(MatchJobDetail(
        id="context", username=owner, run_id=run_id if same_run else "other-search",
        status=state, created_at="2026-09-17T10:00:00Z",
    ))
    response = client.post(
        "/api/messages", headers=auth(client), json=_payload(run_id, match_job_id="context")
    )
    assert response.status_code == expected


def test_requires_auth(client, run_id):
    assert client.post("/api/messages", json=_payload(run_id)).status_code == 401
    assert client.get("/api/messages/options").status_code == 401


def test_options_expose_the_real_channel_limits(client):
    """The UI displays limits from the backend instead of hardcoding a duplicate."""
    body = client.get("/api/messages/options", headers=auth(client)).json()

    connection = next(c for c in body["channels"] if c["id"] == "linkedin_connection")
    assert connection["max_body_chars"] == 300
    assert connection["has_subject"] is False

    inmail = next(c for c in body["channels"] if c["id"] == "linkedin_inmail")
    assert inmail["max_subject_chars"] == 200
    assert inmail["max_body_chars"] == 1900

    assert "vi" in body["languages"]
    assert body["recommended_contacts_per_company"] == 2


def test_empty_target_list_is_rejected(client, run_id):
    resp = client.post("/api/messages", headers=auth(client), json=_payload(run_id, targets=[]))
    assert resp.status_code == 422


def test_unknown_channel_is_rejected(client, run_id):
    resp = client.post(
        "/api/messages", headers=auth(client), json=_payload(run_id, channel="carrier-pigeon")
    )
    assert resp.status_code == 400


def test_unknown_language_is_rejected(client, run_id):
    resp = client.post("/api/messages", headers=auth(client), json=_payload(run_id, language="fr"))
    assert resp.status_code == 400


def test_another_users_run_is_not_reachable(client, run_id):
    bob = auth(client, "bob", "another-pass")
    resp = client.post("/api/messages", headers=bob, json=_payload(run_id))
    assert resp.status_code == 404


def test_job_writes_a_message_for_the_contact(client, run_id):
    headers = auth(client)
    job_id = client.post("/api/messages", headers=headers, json=_payload(run_id)).json()["job_id"]

    final = wait_for_job(client, headers, f"/api/messages/jobs/{job_id}")

    assert final["status"] == "completed"
    assert final["completed"] == 1
    assert final["failed"] == 0

    message = final["results"][0]
    assert message["contact_name"] == "Tran Thi Lan"
    assert message["contact_title"] == "CFO"
    assert message["contact_email"] == "lan@acme.vn"  # From the run, not invented by the LLM.
    assert message["body"] == GOOD_BODY
    assert message["subject"]
    assert message["warnings"] == []


def test_ids_write_to_distinct_recipients_with_duplicate_names(client, configured):
    repo = SQLiteSearchRunRepository(configured)
    run_id = repo.save_run("alice", "apollo", SearchCriteria(), [
        CompanyResult(company=Company(name="Acme", domain=domain), contacts=[
            Contact(full_name="John", email=f"first@{domain}"),
            Contact(full_name="John", email=f"second@{domain}"),
        ]) for domain in ("one.example", "two.example")
    ]).id
    run = repo.get_run("alice", run_id)
    targets = [
        {"company_id": result.company.id, "contact_id": contact.id,
         "company_name": "Acme", "contact_name": "John"}
        for result in run.results for contact in result.contacts
    ]
    headers = auth(client)
    response = client.post("/api/messages", headers=headers, json=_payload(run_id, targets=targets))
    assert response.status_code == 200
    final = wait_for_job(client, headers, f"/api/messages/jobs/{response.json()['job_id']}")
    assert {message["contact_email"] for message in final["results"]} == {
        "first@one.example", "second@one.example", "first@two.example", "second@two.example",
    }


def test_ambiguous_legacy_request_is_rejected_before_creating_a_job(client, configured):
    run_id = SQLiteSearchRunRepository(configured).save_run("alice", "apollo", SearchCriteria(), [
        CompanyResult(company=Company(name="Acme"), contacts=[
            Contact(full_name="John", email="first@example.com"),
            Contact(full_name="John", email="second@example.com"),
        ])
    ]).id
    response = client.post("/api/messages", headers=auth(client), json=_payload(run_id, targets=[
        {"company_name": "Acme", "contact_name": "John"},
    ]))
    assert response.status_code == 400
    assert "ambiguous" in response.json()["detail"]


def test_a_contact_not_in_the_run_is_reported_not_invented(client, run_id):
    """The client cannot add contacts outside the saved data."""
    headers = auth(client)
    job_id = client.post(
        "/api/messages",
        headers=headers,
        json=_payload(
            run_id,
            targets=[{"company_name": "Acme Manufacturing", "contact_name": "Ghost Person"}],
        ),
    ).json()["job_id"]

    final = wait_for_job(client, headers, f"/api/messages/jobs/{job_id}")

    assert final["failed"] == 1
    assert "not in the selected search run" in final["results"][0]["error"]


def test_too_many_contacts_at_one_company_raises_a_notice(client, run_id):
    """Apollo measured lower reply rates when contacting many people at one company."""
    headers = auth(client)
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
    """Two contacts per company is within the recommendation, so a warning would be noise."""
    headers = auth(client)
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
    resp = client.post("/api/messages", headers=auth(client), json=_payload(run_id))
    assert any("No matching run" in n for n in resp.json()["notices"])


def test_job_is_scoped_to_its_owner(client, run_id):
    headers = auth(client)
    job_id = client.post("/api/messages", headers=headers, json=_payload(run_id)).json()["job_id"]

    bob = auth(client, "bob", "another-pass")
    assert client.get(f"/api/messages/jobs/{job_id}", headers=bob).status_code == 404


def test_unknown_job_is_404(client):
    assert client.get("/api/messages/jobs/nope", headers=auth(client)).status_code == 404


def test_jobs_list_shows_history(client, run_id):
    headers = auth(client)
    client.post("/api/messages", headers=headers, json=_payload(run_id))

    jobs = client.get("/api/messages/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["run_id"] == run_id
    assert jobs[0]["channel"] == "email"


def test_rejects_when_there_is_no_sender_profile(db_path, run_id, monkeypatch):
    """Without sender details the LLM would have to invent someone; block it early."""
    monkeypatch.setattr("saletool.messaging.llm.request_json", _fake_write)

    settings = AppSettings()
    settings.llm.api_key = "sk-or-test"
    settings.sender = SenderProfile(full_name="", company_name="")
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    with TestClient(app) as client:
        resp = client.post("/api/messages", headers=auth(client), json=_payload(run_id))

    assert resp.status_code == 400
    assert "Sender profile" in resp.json()["detail"]


def test_rejects_without_an_llm_key(db_path, run_id):
    settings = AppSettings()
    settings.llm.api_key = None
    settings.sender = SenderProfile(full_name="Tran Van A", company_name="ABIM")
    SQLiteSettingsRepository(db_path).save_settings(settings, updated_by="alice")

    with TestClient(app) as client:
        resp = client.post("/api/messages", headers=auth(client), json=_payload(run_id))

    assert resp.status_code == 400
    assert "LLM API key" in resp.json()["detail"]


def test_llm_failure_is_counted_not_fatal(client, run_id, monkeypatch):
    from saletool.llm_api import LLMError

    async def always_fails(*args, **kwargs):
        raise LLMError("provider is down")

    monkeypatch.setattr("saletool.messaging.llm.request_json", always_fails)

    headers = auth(client)
    job_id = client.post("/api/messages", headers=headers, json=_payload(run_id)).json()["job_id"]

    final = wait_for_job(client, headers, f"/api/messages/jobs/{job_id}")

    assert final["status"] == "completed"
    assert final["failed"] == 1
    assert final["results"][0]["error"]
