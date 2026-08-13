"""/api/enrich — chạy pipeline enrich ở nền và tra cứu tiến độ."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from saletool.api import jobs
from saletool.api.deps import get_current_user
from saletool.db.factory import get_enrich_job_repository, get_settings_repository
from saletool.models import EnrichTarget

router = APIRouter(prefix="/api/enrich", tags=["enrich"])

MAX_TARGETS_PER_JOB = 100


class EnrichRequest(BaseModel):
    targets: list[EnrichTarget] = Field(min_length=1)


@router.post("")
async def start_enrich(payload: EnrichRequest, user: str = Depends(get_current_user)) -> dict:
    """Tạo job enrich cho 1 hoặc nhiều công ty. Trả về ngay, client poll trạng thái.

    Phải là `async def`: handler đồng bộ sẽ được FastAPI chạy trong threadpool,
    ở đó không có event loop nên `asyncio.create_task` trong jobs.start_job() sẽ
    lỗi "no running event loop".
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

    job = jobs.create_job(user, payload.targets)
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
