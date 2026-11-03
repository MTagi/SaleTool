"""/api/enrich — run the enrichment pipeline in the background and check progress."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from saletool.api import jobs
from saletool.api.deps import get_current_user
from saletool.db.factory import (
    get_enrich_job_repository,
    get_search_run_repository,
    get_settings_repository,
)
from saletool.history import same_company
from saletool.models import EnrichTarget

router = APIRouter(prefix="/api/enrich", tags=["enrich"])

MAX_TARGETS_PER_JOB = 100


class EnrichRequest(BaseModel):
    targets: list[EnrichTarget] = Field(min_length=1)
    run_id: str | None = None


@router.post("")
async def start_enrich(payload: EnrichRequest, user: str = Depends(get_current_user)) -> dict:
    """Create an enrichment job for one or more companies. Return immediately; the client polls status.

    Must be `async def`: FastAPI runs synchronous handlers in a thread pool, which
    has no event loop, so `asyncio.create_task` in jobs.start_job() would fail with
    "no running event loop".
    """
    if len(payload.targets) > MAX_TARGETS_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many targets (max {MAX_TARGETS_PER_JOB} per job).",
        )

    for target in payload.targets:
        if not target.company_name.strip() and not (target.domain or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each target needs at least a company name or a domain.",
            )

    if payload.run_id:
        run = get_search_run_repository().get_run(user, payload.run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Search run not found.")
        if any(
            not any(
                same_company(item.company.name, item.company.domain, target.company_name, target.domain)
                for item in run.results
            )
            for target in payload.targets
        ):
            raise HTTPException(status_code=400, detail="An enrichment target is not in this search run.")

        for target in payload.targets:
            target.company_profile = next(
                item.company.model_copy(deep=True) for item in run.results
                if same_company(item.company.name, item.company.domain, target.company_name, target.domain)
            )

    settings = get_settings_repository().get_settings()
    enrichment = settings.enrichment

    if not (enrichment.use_company_website or enrichment.use_web_search):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enrichment source is enabled. Turn on company website and/or web search in Settings.",
        )
    if enrichment.use_llm and not settings.llm.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM extraction is enabled but no LLM API key is configured in Settings.",
        )

    job = jobs.create_job(user, payload.targets, run_id=payload.run_id)
    jobs.start_job(job)

    return {"job_id": job.id, "status": job.status, "total": job.total}


@router.get("/jobs")
def list_jobs(user: str = Depends(get_current_user), limit: int = 20) -> list[dict]:
    return [job.model_dump() for job in get_enrich_job_repository().list_jobs(user, limit=limit)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: str = Depends(get_current_user)) -> dict:
    job = get_enrich_job_repository().get_job(user, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrichment job not found.")
    return job.model_dump()
