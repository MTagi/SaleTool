"""/api/status — cái gì đã cấu hình, cái gì đã có dữ liệu.

Một lượt gọi để UI biết trước bước nào chạy được. Trước đây người dùng phải điền
xong cả form rồi bấm mới nhận 400 "chưa có LLM API key" — thông tin đó có sẵn từ
đầu, chỉ là không ai hỏi.

Endpoint trả **dữ kiện**, không trả câu chữ hiển thị: quyết định hiện gì là việc
của frontend, backend chỉ nói sự thật về trạng thái hệ thống.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from saletool.api.deps import get_current_user
from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_message_job_repository,
    get_search_run_repository,
    get_service_repository,
    get_settings_repository,
)

router = APIRouter(prefix="/api/status", tags=["status"])

# Đủ để biết "có hay không" và "khoảng bao nhiêu" mà không kéo cả lịch sử về.
_PROBE_LIMIT = 50


@router.get("")
def read_status(user: str = Depends(get_current_user)) -> dict:
    settings = get_settings_repository().get_settings()
    services = get_service_repository().list_services()

    runs = get_search_run_repository().list_runs(user, limit=_PROBE_LIMIT)
    latest_run = runs[0] if runs else None

    return {
        "llm_configured": bool(settings.llm.api_key),
        "sender_configured": settings.sender.is_usable(),
        "search_provider": settings.search.provider,
        "auto_enrich_on_search": settings.enrichment.auto_enrich_on_search,
        "counts": {
            "services": len(services),
            "active_services": sum(1 for s in services if s.active),
            "runs": len(runs),
            "enrich_jobs": len(get_enrich_job_repository().list_jobs(user, limit=_PROBE_LIMIT)),
            "match_jobs": len(get_match_job_repository().list_jobs(user, limit=_PROBE_LIMIT)),
            "message_jobs": len(get_message_job_repository().list_jobs(user, limit=_PROBE_LIMIT)),
        },
        "latest_run": (
            {
                "id": latest_run.id,
                "created_at": latest_run.created_at,
                "total_companies": latest_run.total_companies,
                "total_contacts": latest_run.total_contacts,
            }
            if latest_run
            else None
        ),
    }
