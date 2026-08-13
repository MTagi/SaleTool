"""Web UI có đăng nhập cho SaleTool (FastAPI + session cookie + SQLite).

Phạm vi: tool nội bộ dùng trong nhóm nhỏ, đứng sau HTTPS reverse proxy đáng tin
cậy. Không có: tự đăng ký công khai, khôi phục mật khẩu, giới hạn số lần đăng
nhập sai, CSRF token riêng — nếu triển khai ra internet công khai, hãy bổ sung
thêm các lớp bảo vệ này.
"""

from __future__ import annotations

import logging
import os
import secrets
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from saletool.models import CompanyResult, SearchCriteria, SENIORITY_LEVELS, DEFAULT_SENIOR_LEVELS
from saletool.output import write_csv, write_json
from saletool.pipeline import run_search
from saletool.providers import get_provider
from saletool.web.users_db import init_db, verify_user

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE_DIR / "templates"))

# Kết quả tìm kiếm gần nhất của mỗi user, lưu tạm trong bộ nhớ tiến trình
# (mất khi restart server — đủ dùng cho 1 phiên làm việc, không cần DB riêng).
_results_store: dict[str, list[CompanyResult]] = {}


def _split_csv_field(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


async def _save_upload(upload) -> Path:
    suffix = Path(upload.filename or "upload.csv").suffix or ".csv"
    fd, path_str = tempfile.mkstemp(suffix=suffix)
    path = Path(path_str)
    content = await upload.read()
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


def create_app() -> FastAPI:
    secret_key = os.environ.get("SALETOOL_SECRET_KEY")
    if not secret_key:
        secret_key = secrets.token_hex(32)
        logger.warning(
            "SALETOOL_SECRET_KEY chưa được đặt — dùng khoá tạm thời, "
            "phiên đăng nhập sẽ mất khi restart server. Đặt biến môi trường "
            "SALETOOL_SECRET_KEY để giữ phiên đăng nhập ổn định."
        )

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        init_db()
        yield

    app = FastAPI(title="SaleTool", lifespan=_lifespan)
    app.add_middleware(SessionMiddleware, secret_key=secret_key, same_site="lax")
    app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        if request.session.get("user"):
            return RedirectResponse("/", status_code=303)
        return _TEMPLATES.TemplateResponse(request, "login.html", {"error": None})

    @app.post("/login", response_class=HTMLResponse)
    def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
        if verify_user(username, password):
            request.session["user"] = username.strip()
            return RedirectResponse("/", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request, "login.html", {"error": "Sai tên đăng nhập hoặc mật khẩu."}, status_code=401
        )

    @app.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        user = request.session.get("user")
        if not user:
            return RedirectResponse("/login", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "error": None,
                "seniority_levels": SENIORITY_LEVELS,
                "default_seniority": DEFAULT_SENIOR_LEVELS,
            },
        )

    @app.post("/search", response_class=HTMLResponse)
    async def do_search(request: Request):
        user = request.session.get("user")
        if not user:
            return RedirectResponse("/login", status_code=303)

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
        except Exception as exc:  # noqa: BLE001 - trả lỗi input rõ ràng cho người dùng
            return _TEMPLATES.TemplateResponse(
                request,
                "dashboard.html",
                {
                    "user": user,
                    "error": f"Tiêu chí không hợp lệ: {exc}",
                    "seniority_levels": SENIORITY_LEVELS,
                    "default_seniority": DEFAULT_SENIOR_LEVELS,
                },
                status_code=400,
            )

        provider_name = field("provider", "mock")
        tmp_paths: list[Path] = []
        try:
            provider_kwargs: dict = {}
            if provider_name == "apollo":
                api_key = field("apollo_api_key")
                if not api_key:
                    raise ValueError("Provider apollo cần API key.")
                provider_kwargs["api_key"] = api_key
            elif provider_name == "csv_import":
                companies_upload = form.get("companies_csv")
                if not companies_upload or not getattr(companies_upload, "filename", None):
                    raise ValueError("Provider csv_import cần file CSV danh sách công ty.")
                companies_path = await _save_upload(companies_upload)
                tmp_paths.append(companies_path)
                provider_kwargs["companies_csv"] = str(companies_path)

                contacts_upload = form.get("contacts_csv")
                if contacts_upload and getattr(contacts_upload, "filename", None):
                    contacts_path = await _save_upload(contacts_upload)
                    tmp_paths.append(contacts_path)
                    provider_kwargs["contacts_csv"] = str(contacts_path)

            provider_instance = get_provider(provider_name, **provider_kwargs)
            results = run_search(criteria, provider_instance)
        except Exception as exc:  # noqa: BLE001 - trả lỗi rõ ràng thay vì 500 trắng
            return _TEMPLATES.TemplateResponse(
                request,
                "dashboard.html",
                {
                    "user": user,
                    "error": f"Không chạy được tìm kiếm: {exc}",
                    "seniority_levels": SENIORITY_LEVELS,
                    "default_seniority": DEFAULT_SENIOR_LEVELS,
                },
                status_code=400,
            )
        finally:
            for p in tmp_paths:
                p.unlink(missing_ok=True)

        _results_store[user] = results
        total_contacts = sum(len(r.contacts) for r in results)
        return _TEMPLATES.TemplateResponse(
            request,
            "results.html",
            {"user": user, "results": results, "total_contacts": total_contacts},
        )

    @app.get("/download/{fmt}")
    def download(request: Request, fmt: str):
        user = request.session.get("user")
        if not user:
            return RedirectResponse("/login", status_code=303)

        results = _results_store.get(user)
        if not results:
            return RedirectResponse("/", status_code=303)
        if fmt not in ("csv", "json"):
            return Response("Định dạng không hỗ trợ.", status_code=400)

        fd, tmp_path_str = tempfile.mkstemp(suffix=f".{fmt}")
        os.close(fd)
        tmp_path = Path(tmp_path_str)
        try:
            if fmt == "json":
                write_json(results, tmp_path)
                media_type = "application/json"
            else:
                write_csv(results, tmp_path)
                media_type = "text/csv"
            data = tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=saletool_results.{fmt}"},
        )

    return app


app = create_app()
