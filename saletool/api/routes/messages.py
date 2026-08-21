"""/api/messages — sinh message gửi cho từng contact, chạy nền."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status

from saletool.api import jobs
from saletool.api.deps import get_current_user
from saletool.db.factory import (
    get_message_job_repository,
    get_search_run_repository,
    get_service_repository,
    get_settings_repository,
)
from saletool.models import (
    MESSAGE_CHANNELS,
    MESSAGE_LANGUAGES,
    MESSAGE_TONES,
    RECOMMENDED_CONTACTS_PER_COMPANY,
    MessageRequest,
)

router = APIRouter(prefix="/api/messages", tags=["messages"])

# Mỗi contact tốn 1 lượt gọi LLM.
MAX_TARGETS_PER_JOB = 50


def _job_notices(request: MessageRequest) -> list[str]:
    """Cảnh báo mức cả job — nói trước khi chạy chứ không để người dùng tự đoán."""
    notices: list[str] = []

    per_company = Counter(t.company_name.strip().lower() for t in request.targets)
    crowded = [name for name, count in per_company.items() if count > RECOMMENDED_CONTACTS_PER_COMPANY]
    if crowded:
        notices.append(
            f"{len(crowded)} company(ies) have more than {RECOMMENDED_CONTACTS_PER_COMPANY} "
            "contacts selected. Apollo's data shows reply rates roughly halve when you contact "
            "many people at the same account instead of one or two."
        )

    if not request.match_job_id:
        notices.append(
            "No matching run selected, so messages are written without a per-company reason "
            "to reach out. Running Matching first makes the opening line much more specific."
        )

    return notices


@router.get("/options")
def message_options(_: str = Depends(get_current_user)) -> dict:
    """Kênh gửi + giới hạn thật của từng kênh, để UI hiển thị đúng mà không chép cứng."""
    return {
        "channels": [
            {
                "id": channel_id,
                "label": spec.label,
                "has_subject": spec.has_subject,
                "max_subject_chars": spec.max_subject_chars,
                "max_body_chars": spec.max_body_chars,
                "max_body_words": spec.max_body_words,
                "guidance": spec.guidance,
            }
            for channel_id, spec in MESSAGE_CHANNELS.items()
        ],
        "tones": MESSAGE_TONES,
        "languages": MESSAGE_LANGUAGES,
        "recommended_contacts_per_company": RECOMMENDED_CONTACTS_PER_COMPANY,
    }


@router.post("")
async def start_messages(payload: MessageRequest, user: str = Depends(get_current_user)) -> dict:
    """Tạo job sinh message. Trả về ngay, client poll trạng thái.

    Phải là `async def` — handler đồng bộ chạy trong threadpool, ở đó
    `asyncio.create_task` sẽ lỗi "no running event loop".
    """
    settings = get_settings_repository().get_settings()
    if not settings.llm.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Writing messages needs an LLM. Configure an LLM API key in Settings first.",
        )
    if not settings.sender.is_usable():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fill in your name and company under Settings → Sender profile first — "
            "a message needs a sender.",
        )

    if payload.channel not in MESSAGE_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown channel: {payload.channel}"
        )
    if payload.tone not in MESSAGE_TONES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown tone: {payload.tone}"
        )
    if payload.language not in MESSAGE_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported language: {payload.language}"
        )
    if len(payload.targets) > MAX_TARGETS_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{len(payload.targets)} contacts selected (max {MAX_TARGETS_PER_JOB} per job).",
        )

    run = get_search_run_repository().get_run(user, payload.run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found.")

    if payload.service_id and not get_service_repository().get_service(payload.service_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service '{payload.service_id}' no longer exists.",
        )

    job = jobs.create_message_job(user, payload, notices=_job_notices(payload))
    jobs.start_message_job(job)

    return {"job_id": job.id, "status": job.status, "total": job.total, "notices": job.notices}


@router.get("/jobs")
def list_jobs(user: str = Depends(get_current_user), limit: int = 20) -> list[dict]:
    return [job.model_dump() for job in get_message_job_repository().list_jobs(user, limit=limit)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: str = Depends(get_current_user)) -> dict:
    job = get_message_job_repository().get_job(user, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message job not found.")
    return job.model_dump()
