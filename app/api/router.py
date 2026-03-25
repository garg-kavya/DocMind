"""
Main API Router
================

Purpose:
    Aggregates all v1 endpoint routers into a single router that is
    mounted on the FastAPI application in main.py.

Route Registration:
    /api/v1/documents   -> documents router (PDF upload/management)
    /api/v1/query       -> query router (question answering)
    /api/v1/sessions    -> sessions router (conversation management)
    /api/v1/health      -> health router (service health)

    All routes are prefixed with /api/v1 for versioning.

Dependencies:
    - fastapi (APIRouter)
    - app.api.v1.documents
    - app.api.v1.query
    - app.api.v1.sessions
    - app.api.v1.health
"""
