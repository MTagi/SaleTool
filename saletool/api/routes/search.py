"""/api/search, /api/search/runs, /api/download/{fmt} — chạy pipeline tìm
công ty + liên hệ cấp cao, và lịch sử các lần chạy trước đó."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from saletool.api.deps import get_current_user
from saletool.db.factory import get_search_run_repository, get_settings_repository
from saletool.models import (
    DATA_PROVIDERS,
    DATA_PROVIDERS_REQUIRING_KEY,
    DEFAULT_SENIOR_LEVELS,
    SENIORITY_LEVELS,
    SearchCriteria,
)
from saletool.output import write_csv, write_json
from saletool.pipeline import run_search
from saletool.providers import get_provider

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search/options")
def search_options(_: str = Depends(get_current_user)) -> dict:
    """Các mức seniority hợp lệ, phục vụ form tìm kiếm.

    Trả từ backend thay vì chép cứng ở frontend: danh sách này là quy ước của
    `saletool/seniority.py`, chép sang JS nghĩa là có hai bản phải nhớ sửa cùng lúc.
    """
    return {
        "seniority_levels": SENIORITY_LEVELS,
        "default_senior_levels": DEFAULT_SENIOR_LEVELS,
        "data_providers": DATA_PROVIDERS,
        # Frontend cần biết provider nào đòi key để nói đúng cái đang thiếu ngay
        # dưới ô chọn, thay vì đoán rằng nguồn nào cũng cần key.
        "data_providers_requiring_key": DATA_PROVIDERS_REQUIRING_KEY,
    }


def _split_csv_field(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


@router.post("/search")
async def search(request: Request, user: str = Depends(get_current_user)) -> dict:
    form = await request.form()

    def field(name: str, default: str = "") -> str:
        value = form.get(name, default)
        return value if isinstance(value, str) else default

    seniority_levels = [v for v in form.getlist("seniority_levels") if isinstance(v, str)]

    try:
        criteria = SearchCriteria(
            industries=_split_csv_field(field("industries")),
            keywords=_split_csv_field(field("keywords")),
            locations=_split_csv_field(field("locations")),
            company_size_min=_parse_optional_int(field("company_size_min")),
            company_size_max=_parse_optional_int(field("company_size_max")),
            target_titles=_split_csv_field(field("target_titles")),
            seniority_levels=seniority_levels or list(DEFAULT_SENIOR_LEVELS),
            max_companies=int(field("max_companies", "20") or 20),
            max_contacts_per_company=int(field("max_contacts_per_company", "5") or 5),
        )
    except Exception as exc:  # bắt rộng để trả lỗi input rõ ràng cho client
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid criteria: {exc}"
        ) from exc

    # Nguồn dữ liệu + API key lấy từ Settings, không lấy từ form: đây là cấu hình
    # một lần của cả đội và được lưu ở dạng mã hoá. Form chỉ còn giữ những thứ
    # thay đổi theo từng lượt chạy (tiêu chí + có tra email hay không).
    data_source = get_settings_repository().get_settings().data_source

    provider_name = field("data_provider") or data_source.provider
    if provider_name not in DATA_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported data provider: {provider_name}",
        )
    if provider_name != data_source.provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{provider_name}' is not the configured data source "
                f"('{data_source.provider}'). Change it in Settings first."
            ),
        )
    if provider_name in DATA_PROVIDERS_REQUIRING_KEY and not data_source.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No API key configured for '{provider_name}'. Add it in Settings.",
        )

    try:
        provider_instance = get_provider(
            provider_name,
            api_key=data_source.api_key,
            # Tra email tốn credit Apollo, nên phải tắt được từ form.
            reveal_emails=field("apollo_reveal_emails", "true") != "false",
        )
        results = run_search(criteria, provider_instance)
    except Exception as exc:  # bắt rộng để trả lỗi rõ ràng thay vì 500 trắng
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Search failed: {exc}"
        ) from exc

    # api_key không nằm trong `criteria` nên không bao giờ bị lưu vào lịch sử.
    run = get_search_run_repository().save_run(
        username=user, provider=provider_name, criteria=criteria, results=results
    )

    return {
        "run_id": run.id,
        "created_at": run.created_at,
        "provider": run.provider,
        "companies": [r.model_dump() for r in results],
        "total_companies": run.total_companies,
        "total_contacts": run.total_contacts,
    }


@router.get("/search/runs")
def list_runs(user: str = Depends(get_current_user), limit: int = 20) -> list[dict]:
    runs = get_search_run_repository().list_runs(user, limit=limit)
    return [r.model_dump() for r in runs]


@router.get("/search/runs/{run_id}")
def get_run(run_id: str, user: str = Depends(get_current_user)) -> dict:
    run = get_search_run_repository().get_run(user, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found.")
    return run.model_dump()


@router.get("/download/{fmt}")
def download(fmt: str, run_id: str | None = None, user: str = Depends(get_current_user)) -> Response:
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported format (use csv or json).")

    repo = get_search_run_repository()
    run = repo.get_run(user, run_id) if run_id else repo.get_latest_run(user)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No search results to download yet.")

    fd, tmp_path_str = tempfile.mkstemp(suffix=f".{fmt}")
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        if fmt == "json":
            write_json(run.results, tmp_path)
            media_type = "application/json"
        else:
            write_csv(run.results, tmp_path)
            media_type = "text/csv"
        data = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=saletool_results.{fmt}"},
    )
