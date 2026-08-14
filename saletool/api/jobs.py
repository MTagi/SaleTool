"""Chạy job nền (enrich, matching) + lưu tiến độ vào DB.

Vì sao chạy nền: enrich 1 công ty mất ~10–30 giây (nhiều trang + LLM), matching
tốn 1 lượt gọi LLM mỗi công ty. Chạy cả danh sách 20 công ty sẽ vượt xa timeout
của một HTTP request. Client tạo job rồi poll trạng thái.

Vì sao dùng asyncio task thay vì Celery/RQ: đây là tool nội bộ nhóm nhỏ, thêm
Redis + worker process là quá nặng so với nhu cầu. Đánh đổi cần biết: **job đang
chạy sẽ mất khi restart server** — nên trạng thái được ghi xuống DB sau mỗi công
ty, và job còn "running" lúc khởi động sẽ được đánh dấu là failed.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_search_run_repository,
    get_settings_repository,
)
from saletool.enrichment import enrich_company
from saletool.matching import build_enrichment_index, lookup_enrichment, match_company, rank_matches
from saletool.models import EnrichJobDetail, EnrichTarget, MatchJobDetail, Service

logger = logging.getLogger(__name__)

# Giữ tham chiếu tới task đang chạy để chúng không bị GC giữa chừng.
_running: set[asyncio.Task] = set()

# Giới hạn số job chạy song song — tránh mở quá nhiều kết nối ra ngoài cùng lúc.
_semaphore = asyncio.Semaphore(2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(username: str, targets: list[EnrichTarget]) -> EnrichJobDetail:
    """Tạo bản ghi job enrich ở trạng thái pending và lưu xuống DB."""
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
    """Khởi chạy job enrich ở nền (fire-and-forget, có giữ tham chiếu)."""
    _spawn(_run_job(job.id, job.username))


def _spawn(coro) -> None:
    """Chạy coroutine ở nền, giữ tham chiếu để task không bị GC giữa chừng."""
    task = asyncio.create_task(coro)
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


# ---------------------------------------------------------------------------
# Job matching: chấm 1 lần search đã lưu với catalog dịch vụ
# ---------------------------------------------------------------------------


def create_match_job(
    username: str, run_id: str, services: list[Service], total: int, objective: str | None = None
) -> MatchJobDetail:
    """Tạo bản ghi job matching ở trạng thái pending và lưu xuống DB.

    `services` được chụp lại nguyên vẹn vào job: sửa hoặc xoá dịch vụ trong
    catalog sau này không được làm sai lệch kết quả đã chạy.
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
    """Khởi chạy job matching ở nền."""
    _spawn(_run_match_job(job.id, job.username))


def _collect_enrichments(username: str, limit: int = 20) -> dict:
    """Gom kết quả enrich gần đây của user để trộn vào hồ sơ công ty.

    Enrich và matching là hai bước tách rời, nên công ty nào đã enrich rồi thì
    ở đây được chấm trên hồ sơ dày hơn hẳn. Không có thì vẫn chấm được, chỉ là
    LLM có ít căn cứ hơn và sẽ tự hạ điểm theo hướng dẫn trong prompt.
    """
    repo = get_enrich_job_repository()
    results = []
    for summary in repo.list_jobs(username, limit=limit):
        detail = repo.get_job(username, summary.id)
        if detail:
            results.extend(detail.results)
    return build_enrichment_index(results)


async def _run_match_job(job_id: str, username: str) -> None:
    repo = get_match_job_repository()

    async with _semaphore:
        job = repo.get_job(username, job_id)
        if not job or job.status not in ("pending", "running"):
            return

        run = get_search_run_repository().get_run(username, job.run_id)
        if not run:
            job.status = "failed"
            job.error = "The search run this job refers to no longer exists."
            job.finished_at = _now()
            repo.update_job(job)
            return

        settings = get_settings_repository().get_settings()
        enrichment_index = _collect_enrichments(username)

        job.status = "running"
        job.started_at = _now()
        repo.update_job(job)

        matches = []
        for result in run.results:
            job.current_target = result.company.name
            repo.update_job(job)

            enrichment = lookup_enrichment(
                enrichment_index, result.company.name, result.company.domain
            )
            try:
                match = await match_company(
                    result, job.services, settings, job.objective, enrichment
                )
            except Exception as exc:  # noqa: BLE001 - 1 công ty lỗi không được làm hỏng cả job
                logger.exception("Matching thất bại cho '%s'", result.company.name)
                job.failed += 1
                job.error = f"{result.company.name}: {exc}"[:500]
            else:
                matches.append(match)
                if match.error:
                    job.failed += 1
                    job.error = f"{result.company.name}: {match.error}"[:500]
                else:
                    job.completed += 1

            # Ghi kết quả đã xếp hạng sau mỗi công ty để client thấy bảng dần
            # hình thành thay vì chờ trắng tới cuối.
            job.results = rank_matches(matches)
            repo.update_job(job)

        job.status = "completed"
        job.current_target = None
        job.finished_at = _now()
        repo.update_job(job)

    logger.info(
        "Job matching %s xong: %d chấm được, %d lỗi", job_id, job.completed, job.failed
    )
