"""SaleTool API — a JSON-only FastAPI service called by the React SPA (frontend/).

Auth: JWT bearer token (no session cookie), suitable for a frontend on another
origin (e.g. Vite dev server :5173) during development.

Security scope: suitable for internal use behind a trusted HTTPS reverse proxy.
Not implemented: failed-login rate limits, token refresh/revocation, and password
recovery. Add these before deploying to the public internet.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from saletool.api import jobs
from saletool.api.routes import auth as auth_routes
from saletool.api.routes import catalog as catalog_routes
from saletool.api.routes import enrich as enrich_routes
from saletool.api.routes import match as match_routes
from saletool.api.routes import messages as message_routes
from saletool.api.routes import search as search_routes
from saletool.api.routes import settings as settings_routes
from saletool.api.routes import status as status_routes

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.recover_interrupted_jobs()
    try:
        yield
    finally:
        await jobs.shutdown_jobs()


def create_app() -> FastAPI:
    app = FastAPI(title="ABIM Sales Assistant API", lifespan=lifespan)

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
    app.include_router(status_routes.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
