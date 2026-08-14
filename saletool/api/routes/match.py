"""/api/match — chấm 1 lần search đã lưu với các dịch vụ được chọn, chạy ở nền."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from saletool.api import jobs
from saletool.api.deps import get_current_user
from saletool.db.factory import (
    get_match_job_repository,
    get_search_run_repository,
    get_service_repository,
    get_settings_repository,
)
from saletool.models import MatchRequest

router = APIRouter(prefix="/api/match", tags=["match"])

# Mỗi công ty tốn 1 lượt gọi LLM. Chặn ở đây để một lần bấm nhầm không đốt hết
# hạn mức API.
MAX_COMPANIES_PER_JOB = 100
MAX_SERVICES_PER_JOB = 20


@router.post("")
async def start_match(payload: MatchRequest, user: str = Depends(get_current_user)) -> dict:
    """Tạo job matching. Trả về ngay, client poll trạng thái.

    Phải là `async def` — xem ghi chú ở routes/enrich.py: handler đồng bộ chạy
    trong threadpool, ở đó `asyncio.create_task` sẽ lỗi "no running event loop".
    """
    settings = get_settings_repository().get_settings()
    if not settings.llm.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Matching needs an LLM. Configure an LLM API key in Settings first.",
        )

    run = get_search_run_repository().get_run(user, payload.run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found."
        )
    if not run.results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That search run has no companies to rank.",
        )
    if len(run.results) > MAX_COMPANIES_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"That run has {len(run.results)} companies (max {MAX_COMPANIES_PER_JOB} per job).",
        )
    if len(payload.service_ids) > MAX_SERVICES_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many services selected (max {MAX_SERVICES_PER_JOB}).",
        )

    repo = get_service_repository()
    services = []
    for service_id in dict.fromkeys(payload.service_ids):
        service = repo.get_service(service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service '{service_id}' no longer exists.",
            )
        services.append(service)

    job = jobs.create_match_job(
        user,
        run_id=payload.run_id,
        services=services,
        total=len(run.results),
        objective=(payload.objective or "").strip() or None,
    )
    jobs.start_match_job(job)

    return {"job_id": job.id, "status": job.status, "total": job.total}


@router.get("/jobs")
def list_jobs(user: str = Depends(get_current_user), limit: int = 20) -> list[dict]:
    return [job.model_dump() for job in get_match_job_repository().list_jobs(user, limit=limit)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: str = Depends(get_current_user)) -> dict:
    job = get_match_job_repository().get_job(user, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match job not found.")
    return job.model_dump()
