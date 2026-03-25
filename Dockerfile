"""
Dockerfile — RAG PDF Q&A Service
==================================

Purpose:
    Multi-stage Docker build for the RAG PDF Q&A application.
    Produces a minimal production image with all dependencies.

Build Stages:

    Stage 1: builder
        - Base: python:3.12-slim
        - Installs build dependencies (gcc, etc. for faiss-cpu, numpy)
        - Installs Python packages from pyproject.toml
        - Compiles any C extensions

    Stage 2: runtime
        - Base: python:3.12-slim
        - Copies installed packages from builder (no build tools)
        - Copies application source code
        - Creates non-root user for security
        - Creates upload and data directories
        - Exposes port 8000

Entrypoint:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

    Single worker because:
    - FAISS index is in-process memory (not shared across workers)
    - Session store is in-process memory
    - Scaling is done at container level (multiple containers)

Environment Variables (required at runtime):
    - OPENAI_API_KEY: OpenAI API key for embeddings and LLM
    - See .env.example for full list

Volumes:
    - /app/uploads: PDF upload storage (mount for persistence)
    - /app/data: Vector store persistence (mount for persistence)

Health Check:
    GET http://localhost:8000/api/v1/health every 30s

Image Size Target: < 500MB
"""

# --- THIS FILE CONTAINS THE DOCKERFILE SPECIFICATION ---
# --- Implementation: standard multi-stage Python build ---
#
# FROM python:3.12-slim AS builder
# WORKDIR /app
# COPY pyproject.toml .
# RUN pip install --no-cache-dir .
#
# FROM python:3.12-slim AS runtime
# COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
# COPY . /app
# WORKDIR /app
# RUN useradd -m appuser && chown -R appuser /app
# USER appuser
# EXPOSE 8000
# HEALTHCHECK CMD curl -f http://localhost:8000/api/v1/health || exit 1
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
