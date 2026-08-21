"""SaleTool API — FastAPI thuần JSON, được React SPA (thư mục frontend/) gọi vào.

Auth: JWT bearer token (không dùng session cookie) — phù hợp frontend chạy ở
origin khác (vd: Vite dev server :5173) trong lúc phát triển.

Phạm vi bảo mật: phù hợp dùng nội bộ sau HTTPS reverse proxy đáng tin cậy.
Chưa có: giới hạn số lần đăng nhập sai, refresh token/thu hồi token, khôi phục
mật khẩu — cần bổ sung nếu triển khai ra internet công khai.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from saletool.api.routes import auth as auth_routes
from saletool.api.routes import catalog as catalog_routes
from saletool.api.routes import enrich as enrich_routes
from saletool.api.routes import match as match_routes
from saletool.api.routes import messages as message_routes
from saletool.api.routes import search as search_routes
from saletool.api.routes import settings as settings_routes

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def create_app() -> FastAPI:
    app = FastAPI(title="ABIM Sales Assistant API")

    origins = [
        origin.strip()
        for origin in os.environ.get("SALETOOL_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_routes.router)
    app.include_router(search_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(enrich_routes.router)
    app.include_router(catalog_routes.router)
    app.include_router(match_routes.router)
    app.include_router(message_routes.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
