"""Chạy job enrich ở nền + lưu tiến độ vào DB.

Vì sao chạy nền: enrich 1 công ty mất ~10–30 giây (nhiều trang + LLM). Auto-enrich
cả danh sách 20 công ty sẽ vượt xa timeout của một HTTP request. Client tạo job
rồi poll trạng thái.

Vì sao dùng asyncio task thay vì Celery/RQ: đây là tool nội bộ nhóm nhỏ, thêm
Redis + worker process là quá nặng so với nhu cầu. Đánh đổi cần biết: **job đang
chạy sẽ mất khi restart server** — nên trạng thái được ghi xuống DB sau mỗi công
ty, và job còn "running" lúc khởi động sẽ được đánh dấu là failed.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from saletool.db.factory import get_enrich_job_repository, get_settings_repository
from saletool.enrichment import enrich_company
from saletool.models import EnrichJobDetail, EnrichTarget

logger = logging.getLogger(__name__)

# Giữ tham chiếu tới task đang chạy để chúng không bị GC giữa chừng.
_running: set[asyncio.Task] = set()

# Giới hạn số job chạy song song — tránh mở quá nhiều kết nối ra ngoài cùng lúc.
_semaphore = asyncio.Semaphore(2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(username: str, targets: list[EnrichTarget]) -> EnrichJobDetail:
    """Tạo bản ghi job ở trạng thái pending và lưu xuống DB."""
    import uuid

    job = EnrichJobDetail(
        id=str(uuid.uuid4()),
        username=username,
        status="pending",
        created_at=_now(),
        total=len(targets),
        targets=targets,
    )
    get_enrich_job_repository().create_job(job)
    return job


def start_job(job: EnrichJobDetail) -> None:
    """Khởi chạy job ở nền (fire-and-forget, có giữ tham chiếu)."""
    task = asyncio.create_task(_run_job(job.id, job.username))
    _running.add(task)
    task.add_done_callback(_running.discard)


async def _run_job(job_id: str, username: str) -> None:
    repo = get_enrich_job_repository()

    async with _semaphore:
        job = repo.get_job(username, job_id)
        if not job or job.status not in ("pending", "running"):
            return

        settings = get_settings_repository().get_settings()

        job.status = "running"
        job.started_at = _now()
        repo.update_job(job)

        for target in job.targets:
            job.current_target = target.company_name
            repo.update_job(job)

            try:
                result = await enrich_company(target, settings)
            except Exception as exc:  # noqa: BLE001 - 1 công ty lỗi không được làm hỏng cả job
                logger.exception("Enrich thất bại cho '%s'", target.company_name)
                job.failed += 1
                job.error = f"{target.company_name}: {exc}"[:500]
            else:
                job.results.append(result)
                job.completed += 1

            repo.update_job(job)

        job.status = "completed"
        job.current_target = None
        job.finished_at = _now()
        repo.update_job(job)

    logger.info(
        "Job enrich %s xong: %d thành công, %d lỗi", job_id, job.completed, job.failed
    )
