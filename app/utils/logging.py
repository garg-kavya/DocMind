"""
Logging Configuration
======================

Purpose:
    Configures structured JSON logging for the application. Structured logs
    enable efficient log aggregation, filtering, and alerting in production.

Configuration:

    Format: JSON lines (one JSON object per log entry)
    Fields per log entry:
        - timestamp: ISO 8601
        - level: DEBUG | INFO | WARNING | ERROR | CRITICAL
        - logger: logger name (module path)
        - message: human-readable message
        - extra: dict of structured context fields

    Contextual Fields (added by middleware/services):
        - request_id: str (unique per request, for tracing)
        - session_id: str (if in a session context)
        - document_id: str (if processing a document)
        - latency_ms: float (for performance tracking)

    Log Levels by Module:
        - app.api.*: INFO (request/response logging)
        - app.services.*: INFO (pipeline stage logging)
        - app.db.*: WARNING (only errors and slow queries)
        - uvicorn: WARNING

Functions:

    setup_logging(log_level: str = "INFO") -> None:
        Configures the root logger with JSON formatting.
        Called once at application startup.

    get_logger(name: str) -> logging.Logger:
        Returns a named logger instance.

Dependencies:
    - logging (stdlib)
    - json (stdlib)
    - Optional: python-json-logger (for JSON formatting)
"""
