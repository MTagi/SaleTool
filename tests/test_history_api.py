"""Saved workflow history survives fresh requests and never crosses ownership."""

import uuid

import mongomock
import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db import mongo_repo, sqlite_repo
from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_message_job_repository,
    get_search_run_repository,
    get_settings_repository,
)
from saletool.models import (
    Company,
    CompanyEnrichment,
    CompanyMatch,
    CompanyResult,
    EnrichJobDetail,
    EnrichTarget,
    GeneratedMessage,
    MatchJobDetail,
    MessageJobDetail,
    SearchCriteria,
    Service,
)
from tests.conftest import auth


@pytest.fixture
def client(db_path):
    with TestClient(app) as client:
        yield client


def save_run(username="alice"):
    return get_search_run_repository().save_run(
        username, "apollo", SearchCriteria(),
        [CompanyResult(company=Company(name="Acme", domain="acme.example"))],
    )


def enrich_job(run_id=None, username="alice", domain="acme.example", description="Saved profile", **kwargs):
    return EnrichJobDetail(
        id=str(uuid.uuid4()), username=username, run_id=run_id,
        created_at=kwargs.pop("created_at", "2026-09-17T10:00:00Z"),
        status="completed", total=1, completed=1,
        targets=[EnrichTarget(company_name="Acme", domain=domain)],
        results=[CompanyEnrichment(company_name="Acme", domain=domain, description=description)],
        **kwargs,
    )


def test_restores_saved_results_and_snapshots_on_fresh_requests(client):
    run = save_run()
    enrich = enrich_job(run.id)
    get_enrich_job_repository().create_job(enrich)
    match = MatchJobDetail(
        id="match", username="alice", run_id=run.id, status="completed",
        created_at="2026-09-17T11:00:00Z", total=1, completed=1,
        services=[Service(id="deleted-service", name="Original service", created_at="x", updated_at="x")],
        results=[CompanyMatch(company_name="Acme", overall_score=85, rank=1)],
    )
    get_match_job_repository().create_job(match)
    message = MessageJobDetail(
        id="message", username="alice", run_id=run.id, status="failed",
        created_at="2026-09-17T12:00:00Z", channel="email", language="vi", tone="direct",
        total=2, completed=1, error="Interrupted",
        results=[GeneratedMessage(company_name="Acme", contact_name="An", channel="email",
                                  language="vi", tone="direct", body="Saved draft")],
    )
    get_message_job_repository().create_job(message)
    headers = auth(client)
    url = f"/api/search/runs/{run.id}/history"
    first = client.get(url, headers=headers)
    assert first.status_code == 200
    data = first.json()
    assert data["enrichments"][0]["description"] == "Saved profile"
    assert data["match_jobs"][0]["results"][0]["overall_score"] == 85
    assert data["match_jobs"][0]["services"][0]["name"] == "Original service"
    assert data["message_jobs"][0]["results"][0]["body"] == "Saved draft"
    # Reload uses only database data, even with no API keys or catalog entries.
    assert client.get(url, headers=headers).json() == data


def test_history_requires_owner_and_excludes_other_users_and_runs(client):
    run = save_run()
    other = save_run()
    repo = get_enrich_job_repository()
    repo.create_job(enrich_job(run.id, username="bob"))
    repo.create_job(enrich_job(other.id))
    get_match_job_repository().create_job(MatchJobDetail(
        id="private", username="bob", run_id=run.id, status="completed", created_at="x"
    ))
    get_message_job_repository().create_job(MessageJobDetail(
        id="unrelated", username="alice", run_id=other.id, status="completed", created_at="x",
        channel="email", language="en", tone="direct"
    ))
    url = f"/api/search/runs/{run.id}/history"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=auth(client, "bob", "another-pass")).status_code == 404
    data = client.get(url, headers=auth(client)).json()
    assert data["enrichments"] == [None]
    assert data["enrich_jobs"] == data["match_jobs"] == data["message_jobs"] == []
    assert client.get("/api/search/runs/missing/history", headers=auth(client)).status_code == 404


def test_legacy_enrichment_domain_matching_latest_and_more_than_twenty_jobs(client):
    run = save_run()
    repo = get_enrich_job_repository()
    legacy = enrich_job(domain="https://www.acme.example/about", description="Legacy")
    legacy.results.append(CompanyEnrichment(company_name="Unrelated", domain="other.example"))
    repo.create_job(legacy)
    repo.create_job(enrich_job(domain="wrong.example", description="Wrong same-name company"))
    for i in range(25):
        repo.create_job(enrich_job(run.id, created_at=f"2026-09-18T00:00:{i:02d}Z", description=f"Version {i}"))
    data = client.get(f"/api/search/runs/{run.id}/history", headers=auth(client)).json()
    assert len(data["enrich_jobs"]) == 26
    assert data["enrichments"][0]["description"] == "Version 24"
    assert data["enrich_jobs"][-1]["results"][0]["description"] == "Legacy"
    assert len(data["enrich_jobs"][-1]["results"]) == 1



def test_delete_run_removes_run_and_linked_jobs_but_keeps_legacy(client):
    run = save_run()
    other = save_run()
    enrich_repo = get_enrich_job_repository()
    linked = enrich_job(run.id)
    enrich_repo.create_job(linked)
    legacy = enrich_job()  # Job without run_id; preserve it after deleting a run.
    enrich_repo.create_job(legacy)
    get_match_job_repository().create_job(MatchJobDetail(
        id="match", username="alice", run_id=run.id, status="completed",
        created_at="2026-09-17T11:00:00Z", total=1, completed=1,
    ))
    get_message_job_repository().create_job(MessageJobDetail(
        id="message", username="alice", run_id=other.id, status="completed",
        created_at="2026-09-17T12:00:00Z", channel="email", language="vi", tone="direct",
    ))

    headers = auth(client)
    assert client.delete(f"/api/search/runs/{run.id}", headers=headers).status_code == 204
    assert get_search_run_repository().get_run("alice", run.id) is None
    assert enrich_repo.get_job("alice", linked.id) is None
    assert enrich_repo.get_job("alice", legacy.id) is not None
    assert get_match_job_repository().get_job("alice", "match") is None
    assert get_message_job_repository().get_job("alice", "message") is not None

    # Repeated deletion and deleting another user's run both fail without exposing its ID.
    assert client.delete(f"/api/search/runs/{run.id}", headers=headers).status_code == 404
    assert client.delete(
        f"/api/search/runs/{other.id}", headers=auth(client, "bob", "another-pass")
    ).status_code == 404
    assert client.delete(f"/api/search/runs/{other.id}").status_code == 401
    # The remaining run is still accessible as usual.
    assert client.get(f"/api/search/runs/{other.id}", headers=headers).status_code == 200
def test_enrichment_start_links_run_and_validates_membership(client, monkeypatch):
    run = save_run()
    settings_repo = get_settings_repository()
    settings = settings_repo.get_settings()
    settings.enrichment.use_llm = False
    settings_repo.save_settings(settings, "alice")
    monkeypatch.setattr("saletool.api.routes.enrich.jobs.start_job", lambda job: None)
    payload = {"run_id": run.id, "targets": [{"company_name": "Acme", "domain": "acme.example"}]}
    headers = auth(client)
    response = client.post("/api/enrich", headers=headers, json=payload)
    assert response.status_code == 200
    job = get_enrich_job_repository().get_job("alice", response.json()["job_id"])
    assert job.run_id == run.id
    assert client.post("/api/enrich", headers=auth(client, "bob", "another-pass"), json=payload).status_code == 404
    payload["targets"][0]["domain"] = "wrong.example"
    assert client.post("/api/enrich", headers=headers, json=payload).status_code == 400


@pytest.mark.parametrize("backend", ["sqlite", "mongo"])
@pytest.mark.parametrize("kind", ["Enrich", "Match", "Message"])
def test_repository_run_filtering_has_no_recent_history_cutoff(tmp_path, backend, kind):
    if backend == "sqlite":
        repo = getattr(sqlite_repo, f"SQLite{kind}JobRepository")(tmp_path / "jobs.db")
    else:
        repo = getattr(mongo_repo, f"Mongo{kind}JobRepository")(
            "mongodb://unused", "test", client=mongomock.MongoClient()
        )
    for i in range(25):
        job = enrich_job("wanted", created_at=f"2026-09-17T00:00:{i:02d}Z")
        if kind == "Match":
            job = MatchJobDetail.model_validate(job.model_dump())
        elif kind == "Message":
            job = MessageJobDetail.model_validate({**job.model_dump(), "channel": "email", "language": "en", "tone": "direct", "results": []})
        repo.create_job(job)
    # Changing JSON-only fields must also change which history owns the job.
    job.run_id = "another"
    repo.update_job(job)
    assert len(repo.list_for_run("alice", "wanted")) == 24
    assert repo.list_for_run("bob", "wanted") == []
    assert repo.list_for_run("alice", "wanted")[0].created_at.endswith("23Z")
    if kind == "Enrich":
        repo.create_job(enrich_job())
        assert len(repo.list_for_run("alice", "wanted", include_unlinked=True)) == 25
