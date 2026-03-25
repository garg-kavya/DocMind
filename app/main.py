"""
FastAPI Application Entry Point
================================

Purpose:
    Initializes and configures the FastAPI application instance. This is the
    single entry point for the entire RAG PDF Q&A service.

Responsibilities:
    - Create the FastAPI app with metadata (title, version, description)
    - Register the v1 API router from app.api.router
    - Mount global middleware (CORS, rate limiting, error handling)
    - Configure application lifespan events:
        * on_startup: initialize vector store connections, warm embedding model,
          load configuration, start session cleanup background task
        * on_shutdown: flush pending writes, close connections, persist state
    - Serve the health endpoint at root level

Inputs:
    - Environment variables and .env file (loaded via app.config)
    - Configuration from configs/default.yaml

Outputs:
    - Running ASGI application accessible via uvicorn

Dependencies:
    - fastapi
    - uvicorn
    - app.api.router (API route registration)
    - app.config (Settings singleton)
    - app.dependencies (shared service instances)
    - app.api.middleware.error_handler (global exception handling)
    - app.api.middleware.rate_limiter (request throttling)

Usage:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
