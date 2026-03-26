"""Centralized Exception Hierarchy — see module docstring in original stub."""
from __future__ import annotations


class AppError(Exception):
    """Base class for all application exceptions."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.request_id: str | None = None


# ---------------------------------------------------------------------------
# Ingestion errors
# ---------------------------------------------------------------------------

class IngestionError(AppError):
    pass

class PDFParsingError(IngestionError):
    pass

class TextExtractionError(IngestionError):
    pass

class ChunkingError(IngestionError):
    pass


# ---------------------------------------------------------------------------
# Embedding errors
# ---------------------------------------------------------------------------

class EmbeddingError(AppError):
    pass

class EmbeddingAPIError(EmbeddingError):
    pass

class EmbeddingTimeoutError(EmbeddingError):
    pass


# ---------------------------------------------------------------------------
# Vector store errors
# ---------------------------------------------------------------------------

class VectorStoreError(AppError):
    pass

class IndexNotFoundError(VectorStoreError):
    pass

class StorageWriteError(VectorStoreError):
    pass

class StorageReadError(VectorStoreError):
    pass


# ---------------------------------------------------------------------------
# Retrieval errors
# ---------------------------------------------------------------------------

class RetrievalError(AppError):
    pass

class NoDocumentsError(RetrievalError):
    pass

class RerankerError(RetrievalError):
    pass


# ---------------------------------------------------------------------------
# Generation errors
# ---------------------------------------------------------------------------

class GenerationError(AppError):
    pass

class GenerationAPIError(GenerationError):
    pass

class GenerationTimeoutError(GenerationError):
    pass

class ContextTooLongError(GenerationError):
    pass

class CitationExtractionError(GenerationError):
    pass


# ---------------------------------------------------------------------------
# Session errors
# ---------------------------------------------------------------------------

class SessionError(AppError):
    pass

class SessionNotFoundError(SessionError):
    pass

class SessionExpiredError(SessionError):
    pass

class SessionCapacityError(SessionError):
    pass


# ---------------------------------------------------------------------------
# Document errors
# ---------------------------------------------------------------------------

class DocumentError(AppError):
    pass

class DocumentNotFoundError(DocumentError):
    pass

class DocumentNotReadyError(DocumentError):
    pass


# ---------------------------------------------------------------------------
# Cache errors (non-fatal)
# ---------------------------------------------------------------------------

class CacheError(AppError):
    pass

class CacheReadError(CacheError):
    pass

class CacheWriteError(CacheError):
    pass


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class ValidationError(AppError):
    pass

class FileTooLargeError(ValidationError):
    pass

class InvalidFileTypeError(ValidationError):
    pass

class InvalidQueryError(ValidationError):
    pass
