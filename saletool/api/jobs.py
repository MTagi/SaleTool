"""Run background jobs (enrichment, matching, messaging) and save progress to the database.

Why background jobs: enriching one company takes ~10–30 seconds (multiple pages
and an LLM); matching and messaging make one LLM call per company/contact. A full
list takes longer than an HTTP request timeout. The client creates a job and polls
its status.

Why asyncio tasks instead of Celery/RQ: this is a small-team internal tool, and
adding Redis and worker processes would be excessive. The trade-off is that
**running jobs are lost on server restart**. Progress is saved after each company,
and jobs still marked "running" at startup are marked failed.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from saletool.clock import now_iso
from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_message_job_repository,
    get_search_run_repository,
    get_settings_repository,
)
from saletool.enrichment import enrich_company
from saletool.identity import lookup_company_match, resolve_message_target
from saletool.matching import (
    build_enrichment_index,
    lookup_enrichment,
    match_company,
    rank_matches,
)
from saletool.messaging import generate_message
from saletool.models import (
    ACTIVE_JOB_STATUSES,
    CompanyMatch,
    EnrichJobDetail,
    EnrichTarget,
    GeneratedMessage,
    MatchJobDetail,
    MessageJobDetail,
    MessageRequest,
    Service,
)

logger = logging.getLogger(__name__)

# Keep references to running tasks so they are not garbage-collected prematurely.
_running: set[asyncio.Task] = set()

# Limit concurrent jobs to avoid opening too many external connections at once.
_semaphore = asyncio.Semaphore(2)


def _now() -> str:
    """Strictly increasing timestamp; list_jobs sorts by created_at."""
    return now_iso()


class JobProgress:
    """Persist a job's lifecycle and progress to the database.

    All three runners follow the same sequence: claim the job -> mark it running
    -> for each item, record what is being processed, run it, record success or
    failure -> close the job. Previously each runner repeated this with scattered
    `job.x = ...` and `repo.update_job(job)` pairs, making a save easy to miss.

    Saving after **every** item is intentional: the UI can poll a gradually
    filling table, and completed results survive if the server stops mid-job.
    """

    def __init__(self, repo, job) -> None:
        self._repo = repo
        self.job = job

    def start(self) -> None:
        self.job.status = "running"
        self.job.started_at = _now()
        self.save()

    def working_on(self, label: str) -> None:
        self.job.current_target = label
        self.save()

    def succeeded(self) -> None:
        self.job.completed += 1
        self.save()

    def failed(self, label: str, reason: object) -> None:
        """Count a failure. `error` stores the *most recent* error, not the only one."""
        self.job.failed += 1
        self.job.error = f"{label}: {reason}"[:500]
        self.save()

    def finish(self) -> None:
        self.job.status = "completed"
        self.job.current_target = None
        self.job.finished_at = _now()
        self.save()

    def abort(self, reason: str) -> None:
        """The job could not run at all, unlike a completed job with failed items."""
        self.job.status = "failed"
        self.job.error = reason
        self.job.current_target = None
        self.job.finished_at = _now()
        self.save()

    def save(self) -> None:
        """Save the job after the runner updates its payload."""
        self._repo.update_job(self.job)


def _claim(repo, username: str, job_id: str) -> JobProgress | None:
    """Claim a job to run, or return None if it has finished or been cancelled.

    This check is necessary: job creation and execution happen in different
    places, so its status may change before the task actually starts.
    """
    job = repo.get_job(username, job_id)
    if not job or job.status not in ACTIVE_JOB_STATUSES:
        return None
    return JobProgress(repo, job)


def create_job(
    username: str, targets: list[EnrichTarget], run_id: str | None = None
) -> EnrichJobDetail:
    """Create and persist an enrichment job in the pending state."""
    job = EnrichJobDetail(
        id=str(uuid.uuid4()),
        username=username,
        status="pending",
        created_at=_now(),
        total=len(targets),
        targets=targets,
        run_id=run_id,
    )
    get_enrich_job_repository().create_job(job)
    return job


def start_job(job: EnrichJobDetail) -> None:
    """Start an enrichment job in the background (fire-and-forget, retaining a reference)."""
    _spawn(lambda: _run_job(job.id, job.username), job, get_enrich_job_repository)


def _spawn(runner, job, repository_factory) -> None:
    """Run a coroutine in the background and retain it to prevent premature garbage collection."""
    task = asyncio.create_task(_guard_job(runner, job, repository_factory))
    _running.add(task)

    def done(task):
        _running.discard(task)
        # The task may be cancelled before the coroutine executes its first statement.
        if task.cancelled():
            _abort_background_job(
                job, repository_factory, "The server stopped. Start this job again."
            )

    task.add_done_callback(done)


async def _guard_job(runner, job, repository_factory) -> None:
    """Close the job if an error occurs outside the item loop or during server shutdown."""
    try:
        await runner()
    except asyncio.CancelledError:
        _abort_background_job(job, repository_factory, "The server stopped. Start this job again.")
        raise
    except Exception:
        logger.exception("Job %s ended unexpectedly", job.id)
        _abort_background_job(
            job, repository_factory, "The job stopped unexpectedly. Start it again."
        )


def _abort_background_job(job, repository_factory, reason: str) -> None:
    try:
        repo = repository_factory()
        saved = repo.get_job(job.username, job.id)
        if saved and saved.status in ACTIVE_JOB_STATUSES:
            saved.current_target = None
            JobProgress(repo, saved).abort(reason)
    except Exception:
        logger.exception("Could not save the final state of job %s", job.id)


def recover_interrupted_jobs() -> None:
    """The previous process lost the in-memory task; keep results but close its state."""
    finished_at = _now()
    reason = "The server restarted before this job finished. Start it again."
    for factory in (
        get_enrich_job_repository,
        get_match_job_repository,
        get_message_job_repository,
    ):
        factory().fail_active_jobs(reason, finished_at)


async def shutdown_jobs() -> None:
    tasks = list(_running)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _message_requests.clear()


async def _run_job(job_id: str, username: str) -> None:
    async with _semaphore:
        progress = _claim(get_enrich_job_repository(), username, job_id)
        if progress is None:
            return
        job = progress.job

        settings = get_settings_repository().get_settings()
        progress.start()

        for target in job.targets:
            progress.working_on(target.company_name)
            try:
                result = await enrich_company(target, settings)
            except Exception as exc:
                logger.exception("Enrichment failed for '%s'", target.company_name)
                progress.failed(target.company_name, exc)
            else:
                job.results.append(result)
                progress.succeeded()

        progress.finish()

    logger.info("Enrichment job %s finished: %d succeeded, %d failed", job_id, job.completed, job.failed)


# ---------------------------------------------------------------------------
# Matching job: score a saved search run against the service catalog.
# ---------------------------------------------------------------------------


def create_match_job(
    username: str, run_id: str, services: list[Service], total: int, objective: str | None = None
) -> MatchJobDetail:
    """Create and persist a matching job in the pending state.

    `services` are snapshotted in the job so later catalog edits or deletions do
    not alter its results.
    """
    job = MatchJobDetail(
        id=str(uuid.uuid4()),
        username=username,
        status="pending",
        created_at=_now(),
        run_id=run_id,
        objective=objective,
        total=total,
        services=services,
    )
    get_match_job_repository().create_job(job)
    return job


def start_match_job(job: MatchJobDetail) -> None:
    """Start a matching job in the background."""
    _spawn(lambda: _run_match_job(job.id, job.username), job, get_match_job_repository)


def _collect_enrichments(username: str, limit: int = 20) -> dict:
    """Collect the user's recent enrichment results to augment company profiles.

    Enrichment and matching are separate steps, so previously enriched companies
    are scored with richer profiles. Scoring still works without enrichment, but
    the LLM has less evidence and will lower scores as directed by the prompt.
    """
    repo = get_enrich_job_repository()
    results = []
    for summary in repo.list_jobs(username, limit=limit):
        detail = repo.get_job(username, summary.id)
        if detail:
            results.extend(detail.results)
    return build_enrichment_index(results)


async def _run_match_job(job_id: str, username: str) -> None:
    async with _semaphore:
        progress = _claim(get_match_job_repository(), username, job_id)
        if progress is None:
            return
        job = progress.job

        run = get_search_run_repository().get_run(username, job.run_id)
        if not run:
            progress.abort("The search run this job refers to no longer exists.")
            return

        settings = get_settings_repository().get_settings()
        enrichment_index = _collect_enrichments(username)
        progress.start()

        matches: list[CompanyMatch] = []
        for result in run.results:
            progress.working_on(result.company.name)

            enrichment = lookup_enrichment(
                enrichment_index, result.company.name, result.company.domain
            )
            try:
                match = await match_company(
                    result, job.services, settings, job.objective, enrichment
                )
            except Exception as exc:
                logger.exception("Matching failed for '%s'", result.company.name)
                progress.failed(result.company.name, exc)
            else:
                matches.append(match)
                # Keep companies with scoring errors in the results (at the end),
                # but count them as failures: a low score differs from no score.
                if match.error:
                    progress.failed(result.company.name, match.error)
                else:
                    progress.succeeded()

            # Save rankings after each company so the client sees the table fill
            # in instead of waiting for a blank screen until the end.
            job.results = rank_matches(matches)
            progress.save()

        progress.finish()

    logger.info("Matching job %s finished: %d scored, %d failed", job_id, job.completed, job.failed)


# ---------------------------------------------------------------------------
# Message generation job for contacts.
# ---------------------------------------------------------------------------


def create_message_job(
    username: str, request: MessageRequest, notices: list[str] | None = None
) -> MessageJobDetail:
    job = MessageJobDetail(
        id=str(uuid.uuid4()),
        username=username,
        status="pending",
        created_at=_now(),
        run_id=request.run_id,
        channel=request.channel,
        language=request.language,
        tone=request.tone,
        total=len(request.targets),
        notices=notices or [],
    )
    get_message_job_repository().create_job(job)
    _message_requests[job.id] = request
    return job


# Job parameters (recipients, service, and additional instructions) are only
# needed at runtime, so keep them in memory; the job itself is in the database.
# Pending jobs lose these parameters on server restart, the same trade-off as
# other background jobs here.
_message_requests: dict[str, MessageRequest] = {}


def start_message_job(job: MessageJobDetail) -> None:
    _spawn(lambda: _run_message_job(job.id, job.username), job, get_message_job_repository)


def _not_in_run(job: MessageJobDetail, target) -> GeneratedMessage:
    """Placeholder for a contact missing from the run; it must still appear in results."""
    return GeneratedMessage(
        company_id=target.company_id,
        contact_id=target.contact_id,
        company_name=target.company_name,
        contact_name=target.contact_name,
        channel=job.channel,
        language=job.language,
        tone=job.tone,
        error="This contact is not in the selected search run.",
    )


async def _run_message_job(job_id: str, username: str) -> None:
    from saletool.db.factory import get_service_repository

    request = _message_requests.pop(job_id, None)

    async with _semaphore:
        progress = _claim(get_message_job_repository(), username, job_id)
        if progress is None:
            return
        job = progress.job

        if not request:
            progress.abort(
                "The job parameters were lost (was the server restarted?). Start it again."
            )
            return

        run = get_search_run_repository().get_run(username, job.run_id)
        if not run:
            progress.abort("The search run this job refers to no longer exists.")
            return

        settings = get_settings_repository().get_settings()

        # Additional context: enrichment (company description) and matching
        # (reason for fit). Messages can still be written without either, but
        # will be more generic.
        enrichment_index = _collect_enrichments(username)
        matches: list[CompanyMatch] = []
        if request.match_job_id:
            match_job = get_match_job_repository().get_job(username, request.match_job_id)
            if match_job:
                matches = match_job.results

        # Use the service specified by the user, or the best-matching service for
        # each company if none was specified.
        forced_service = (
            get_service_repository().get_service(request.service_id) if request.service_id else None
        )
        service_cache: dict[str, Service | None] = {}

        def service_for(match: CompanyMatch | None) -> Service | None:
            if forced_service is not None:
                return forced_service
            if match is None or not match.best_service_id:
                return None
            if match.best_service_id not in service_cache:
                service_cache[match.best_service_id] = get_service_repository().get_service(
                    match.best_service_id
                )
            return service_cache[match.best_service_id]

        progress.start()

        for target in request.targets:
            label = f"{target.contact_name} ({target.company_name})"
            progress.working_on(label)

            try:
                result, contact = resolve_message_target(run, target)
            except ValueError as exc:
                message = _not_in_run(job, target)
                message.error = str(exc)
                job.results.append(message)
                progress.failed(label, exc)
                continue
            if not result or not contact:
                job.results.append(_not_in_run(job, target))
                progress.failed(label, "not in the selected search run")
                continue

            match = lookup_company_match(matches, result)
            enrichment = lookup_enrichment(
                enrichment_index, result.company.name, result.company.domain
            )

            try:
                message = await generate_message(
                    company=result.company,
                    contact=contact,
                    settings=settings,
                    channel=job.channel,
                    language=job.language,
                    tone=job.tone,
                    service=service_for(match),
                    enrichment=enrichment,
                    match=match,
                    custom_instructions=request.custom_instructions,
                )
            except Exception as exc:
                logger.exception("Message generation failed for '%s'", target.contact_name)
                progress.failed(target.contact_name, exc)
            else:
                job.results.append(message)
                # A generated message that violates channel limits is also a
                # failure: it cannot be sent, even though the model returned it.
                if message.error:
                    progress.failed(target.contact_name, message.error)
                else:
                    progress.succeeded()

        progress.finish()

    logger.info("Message job %s finished: %d generated, %d failed", job_id, job.completed, job.failed)
