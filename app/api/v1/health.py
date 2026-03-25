"""
Health Check Endpoint
======================

Purpose:
    Provides service health and readiness information for monitoring,
    load balancers, and container orchestration (Docker/K8s).

Endpoints:

    GET /api/v1/health
        Returns the overall health status of the service.

        Response: 200 OK
            {
                "status": "healthy",
                "version": "0.1.0",
                "checks": {
                    "vector_store": "ok" | "error",
                    "openai_api": "ok" | "error",
                    "upload_dir": "ok" | "error"
                },
                "uptime_seconds": float,
                "active_sessions": int,
                "total_documents": int,
                "total_vectors": int
            }

        Response: 503 Service Unavailable (if any critical check fails)
            Same schema with status="unhealthy"

    Health Checks Performed:
        - vector_store: Can the vector DB be reached and queried?
        - openai_api: Is the API key valid? (cached check, refreshed every 60s)
        - upload_dir: Does the upload directory exist and is it writable?

Dependencies:
    - fastapi (APIRouter, Depends)
    - app.dependencies (get_vector_store, get_settings)
    - time (for uptime tracking)
"""
