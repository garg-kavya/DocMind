"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from pgvector.asyncpg import register_vector
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.middleware.error_handler import app_error_handler, generic_error_handler
from app.api.middleware.rate_limiter import RateLimiterMiddleware
from app.api.router import api_router
from app.config import get_settings
from app.dependencies import build_app_state
from app.exceptions import AppError
from app.utils.file_utils import ensure_directory
from app.utils.logging import get_logger, setup_logging

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)

    # Ensure directories exist
    ensure_directory(settings.upload_dir)
    ensure_directory(settings.vector_store_path)

    # Build and attach object graph
    state = build_app_state(settings)
    for key, value in state.items():
        setattr(app.state, key, value)

    # Step 1: enable pgvector extension using a single bootstrap connection
    # (must exist before the pool registers the vector codec on each connection)
    _boot = await asyncpg.connect(settings.database_url)
    await _boot.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await _boot.close()

    # Step 2: connection pool — register_vector codec on every new connection
    pg_pool = await asyncpg.create_pool(
        settings.database_url, min_size=2, max_size=10, init=register_vector
    )

    # Step 3: inject pool into all PostgreSQL-backed stores
    app.state.vector_store._pool = pg_pool
    app.state.user_store._pool = pg_pool
    app.state.token_blocklist._pool = pg_pool
    app.state.password_reset_store._pool = pg_pool

    # Step 4: initialize schemas + restore persisted state
    await app.state.vector_store.initialize()
    await app.state.document_registry.load_from_disk()
    await app.state.session_store.load_from_disk()
    await app.state.user_store.create_table()
    await app.state.token_blocklist.create_table()
    await app.state.password_reset_store.create_table()
    logger.info("DocMind service started")

    # Background: periodic session cleanup + blocklist pruning
    async def _cleanup_loop():
        store = app.state.session_store
        blocklist = app.state.token_blocklist
        reset_store = app.state.password_reset_store
        while True:
            await asyncio.sleep(settings.session_cleanup_interval_seconds)
            removed = await store.cleanup_expired()
            if removed:
                logger.info("Cleaned up %d expired sessions", removed)
            await blocklist.cleanup_expired()
            await reset_store.cleanup_expired()

    cleanup_task = asyncio.create_task(_cleanup_loop())

    yield  # app is running

    cleanup_task.cancel()
    await pg_pool.close()
    logger.info("DocMind service shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="DocMind — AI-powered PDF Q&A with conversational memory",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    app.add_middleware(RateLimiterMiddleware)

    # Error handlers
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_error_handler)

    # Serve frontend: root route first, then static assets, then API
    if os.path.isdir(_FRONTEND_DIR):
        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))

    # API routes
    app.include_router(api_router)

    # Static files — must come before the 404 handler below
    if os.path.isdir(_FRONTEND_DIR):
        app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="frontend_static")

    # SPA fallback — use a 404 handler so static files and API routes are never intercepted.
    # Routes always win over mounts in FastAPI, so a catch-all GET route would shadow /static/*.
    # A 404 handler fires only when nothing else matched, which is exactly what we want.
    if os.path.isdir(_FRONTEND_DIR):
        @app.exception_handler(404)
        async def spa_fallback(request: Request, exc: Exception) -> FileResponse | JSONResponse:
            path = request.url.path
            # Let API and static 404s return JSON so they're machine-readable
            if path.startswith("/api/") or path.startswith("/static/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))

    return app


app = create_app()
