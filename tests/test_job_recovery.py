import asyncio
from unittest.mock import Mock

import mongomock
import pytest
from fastapi.testclient import TestClient

from saletool.api import jobs
from saletool.api.app import create_app
from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_message_job_repository,
)
from saletool.models import CompanyEnrichment, EnrichJobDetail, MatchJobDetail, MessageJobDetail


@pytest.mark.parametrize("backend", ["sqlite", "mongo"])
def test_startup_closes_interrupted_jobs_and_preserves_saved_results(db_path, monkeypatch, backend):
    if backend == "mongo":
        from saletool.db import mongo_repo

        client = mongomock.MongoClient()
        monkeypatch.setenv("SALETOOL_DB_BACKEND", "mongo")
        monkeypatch.setattr(mongo_repo, "_connect", lambda *args: client)
    factories = [get_enrich_job_repository, get_match_job_repository, get_message_job_repository]
    models = [EnrichJobDetail, MatchJobDetail, MessageJobDetail]
    for factory, model in zip(factories, models, strict=True):
        for status in ("pending", "running", "completed", "failed"):
            job = model(
                id=status,
                username="alice",
                status=status,
                created_at="now",
                run_id="run",
                channel="email",
                language="en",
                tone="direct",
            )
            if model is EnrichJobDetail:
                job.results = [CompanyEnrichment(company_name="Acme", description="Saved data")]
                job.completed = 1
            job.current_target = "Acme" if status == "running" else None
            factory().create_job(job)
    with TestClient(create_app()):
        for factory in factories:
            for status in ("pending", "running"):
                job = factory().get_job("alice", status)
                assert job.status == "failed"
                assert job.finished_at and job.current_target is None
                assert "restarted" in job.error
            assert factory().get_job("alice", "completed").status == "completed"
            assert factory().get_job("alice", "failed").error is None
        saved = get_enrich_job_repository().get_job("alice", "running")
        assert saved.completed == 1 and saved.results[0].description == "Saved data"


def test_unexpected_setup_failure_does_not_leave_job_pending(db_path, monkeypatch):
    settings_repo = Mock()
    settings_repo.get_settings.side_effect = RuntimeError("Broken settings")
    monkeypatch.setattr(jobs, "get_settings_repository", lambda: settings_repo)
    job = jobs.create_job("alice", [])

    async def run():
        jobs.start_job(job)
        await asyncio.gather(*jobs._running)

    asyncio.run(run())
    final = get_enrich_job_repository().get_job("alice", job.id)
    assert final.status == "failed" and final.finished_at


def test_shutdown_closes_even_a_task_cancelled_before_it_starts(db_path):
    job = jobs.create_job("alice", [])

    async def run():
        jobs.start_job(job)
        await jobs.shutdown_jobs()

    asyncio.run(run())
    assert get_enrich_job_repository().get_job("alice", job.id).status == "failed"
