"""Chạy job nền (enrich, matching, message) + lưu tiến độ vào DB.

Vì sao chạy nền: enrich 1 công ty mất ~10–30 giây (nhiều trang + LLM); matching
và message tốn 1 lượt gọi LLM mỗi công ty/contact. Chạy cả danh sách sẽ vượt xa
timeout của một HTTP request. Client tạo job rồi poll trạng thái.

Vì sao dùng asyncio task thay vì Celery/RQ: đây là tool nội bộ nhóm nhỏ, thêm
Redis + worker process là quá nặng so với nhu cầu. Đánh đổi cần biết: **job đang
chạy sẽ mất khi restart server** — nên trạng thái được ghi xuống DB sau mỗi công
ty, và job còn "running" lúc khởi động sẽ được đánh dấu là failed.
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

# Giữ tham chiếu tới task đang chạy để chúng không bị GC giữa chừng.
_running: set[asyncio.Task] = set()

# Giới hạn số job chạy song song — tránh mở quá nhiều kết nối ra ngoài cùng lúc.
_semaphore = asyncio.Semaphore(2)


def _now() -> str:
    """Mốc thời gian tăng nghiêm ngặt — list_jobs sắp xếp theo created_at."""
    return now_iso()


def _key(name: str) -> str:
    """Khoá so khớp tên công ty/người: bỏ khoảng trắng thừa, không phân biệt hoa thường."""
    return name.strip().lower()


class JobProgress:
    """Ghi vòng đời và tiến độ của một job xuống DB.

    Cả ba runner đều đi đúng một trình tự: nhận job -> đánh dấu running -> với
    mỗi phần tử thì ghi "đang làm cái này", chạy, ghi thành công hoặc thất bại
    -> đóng lại. Trước đây mỗi runner tự viết lại trình tự đó bằng những cặp
    `job.x = ...` + `repo.update_job(job)` rải rác, và rất dễ quên một lần ghi.

    Ghi sau **mỗi** phần tử là cố ý: đó là thứ cho phép UI poll ra một bảng đang
    dần đầy, và cũng là thứ giữ lại được kết quả đã chạy khi server chết giữa
    chừng.
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
        """Đếm một thất bại. `error` là lỗi *gần nhất*, không phải lỗi duy nhất."""
        self.job.failed += 1
        self.job.error = f"{label}: {reason}"[:500]
        self.save()

    def finish(self) -> None:
        self.job.status = "completed"
        self.job.current_target = None
        self.job.finished_at = _now()
        self.save()

    def abort(self, reason: str) -> None:
        """Job không chạy được chút nào — khác hẳn với chạy xong mà có phần tử lỗi."""
        self.job.status = "failed"
        self.job.error = reason
        self.job.finished_at = _now()
        self.save()

    def save(self) -> None:
        """Ghi job xuống DB sau khi runner tự sửa phần payload của nó."""
        self._repo.update_job(self.job)


def _claim(repo, username: str, job_id: str) -> JobProgress | None:
    """Nhận job để chạy, hoặc None nếu nó đã xong/đã huỷ.

    Kiểm tra này không thừa: job được tạo và được chạy ở hai chỗ khác nhau, nên
    tới lúc task thực sự chạy thì trạng thái có thể đã đổi.
    """
    job = repo.get_job(username, job_id)
    if not job or job.status not in ACTIVE_JOB_STATUSES:
        return None
    return JobProgress(repo, job)


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
                logger.exception("Enrich thất bại cho '%s'", target.company_name)
                progress.failed(target.company_name, exc)
            else:
                job.results.append(result)
                progress.succeeded()

        progress.finish()

    logger.info("Job enrich %s xong: %d thành công, %d lỗi", job_id, job.completed, job.failed)


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
                logger.exception("Matching thất bại cho '%s'", result.company.name)
                progress.failed(result.company.name, exc)
            else:
                matches.append(match)
                # Công ty chấm lỗi vẫn nằm trong kết quả (xếp cuối bảng), nhưng
                # đếm là thất bại — "điểm thấp" và "không chấm được" là hai việc.
                if match.error:
                    progress.failed(result.company.name, match.error)
                else:
                    progress.succeeded()

            # Ghi kết quả đã xếp hạng sau mỗi công ty để client thấy bảng dần
            # hình thành thay vì chờ trắng tới cuối.
            job.results = rank_matches(matches)
            progress.save()

        progress.finish()

    logger.info("Job matching %s xong: %d chấm được, %d lỗi", job_id, job.completed, job.failed)


# ---------------------------------------------------------------------------
# Job sinh message gửi contact
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


# Tham số của job (danh sách người nhận, dịch vụ, hướng dẫn thêm) chỉ cần trong
# lúc chạy nên giữ trong bộ nhớ; bản thân job đã nằm trong DB. Restart server
# thì job pending mất tham số — cùng đánh đổi với các job nền khác ở đây.
_message_requests: dict[str, MessageRequest] = {}


def start_message_job(job: MessageJobDetail) -> None:
    _spawn(_run_message_job(job.id, job.username))


def _find_contact(result, contact_name: str):
    """Tìm contact theo tên trong một công ty của search run. None nếu không có."""
    wanted = _key(contact_name)
    return next((c for c in result.contacts if _key(c.full_name) == wanted), None)


def _not_in_run(job: MessageJobDetail, target) -> GeneratedMessage:
    """Chỗ giữ chỗ cho contact không còn trong run — vẫn phải hiện ra ở bảng kết quả."""
    return GeneratedMessage(
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

        # Ngữ cảnh phụ: enrich (mô tả công ty) và matching (lý do phù hợp).
        # Thiếu cái nào thì message vẫn viết được, chỉ chung chung hơn.
        enrichment_index = _collect_enrichments(username)
        matches: dict[str, CompanyMatch] = {}
        if request.match_job_id:
            match_job = get_match_job_repository().get_job(username, request.match_job_id)
            if match_job:
                matches = {_key(m.company_name): m for m in match_job.results}

        # Người dùng ép một dịch vụ cụ thể, hoặc để trống thì lấy dịch vụ khớp
        # nhất của từng công ty theo kết quả matching.
        forced_service = (
            get_service_repository().get_service(request.service_id)
            if request.service_id
            else None
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

        companies = {_key(r.company.name): r for r in run.results}
        progress.start()

        for target in request.targets:
            label = f"{target.contact_name} ({target.company_name})"
            progress.working_on(label)

            result = companies.get(_key(target.company_name))
            contact = _find_contact(result, target.contact_name) if result else None
            if not result or not contact:
                job.results.append(_not_in_run(job, target))
                progress.failed(label, "not in the selected search run")
                continue

            match = matches.get(_key(result.company.name))
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
                logger.exception("Sinh message thất bại cho '%s'", target.contact_name)
                progress.failed(target.contact_name, exc)
            else:
                job.results.append(message)
                # Message viết ra nhưng vi phạm giới hạn kênh cũng là thất bại —
                # nó không gửi được, dù model đã trả lời.
                if message.error:
                    progress.failed(target.contact_name, message.error)
                else:
                    progress.succeeded()

        progress.finish()

    logger.info("Job message %s xong: %d viết được, %d lỗi", job_id, job.completed, job.failed)
