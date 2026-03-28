"""Document registry with in-memory state and JSON persistence."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

from app.exceptions import DocumentNotFoundError
from app.models.document import Document
from app.schemas.metadata import IngestionMetadata, PDFMetadata
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentRegistry:

    def __init__(self, persist_path: str | None = None) -> None:
        self._docs: dict[str, Document] = {}
        self._lock = asyncio.Lock()
        self._persist_path = persist_path

    async def register(
        self,
        document_id: str,
        filename: str,
        file_path: str,
        file_size_bytes: int,
        user_id: str = "",
    ) -> Document:
        doc = Document(
            document_id=document_id,
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            user_id=user_id,
            status="uploaded",
        )
        async with self._lock:
            self._docs[document_id] = doc
        return doc

    async def update_status(
        self,
        document_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        async with self._lock:
            doc = self._docs.get(document_id)
            if doc is None:
                return
            doc.status = status
            doc.error_message = error_message
            if status in ("ready", "error"):
                doc.processed_at = datetime.utcnow()

    async def set_ingestion_metadata(
        self,
        document_id: str,
        pdf_metadata: PDFMetadata,
        ingestion_metadata: IngestionMetadata,
    ) -> None:
        async with self._lock:
            doc = self._docs.get(document_id)
            if doc is None:
                return
            doc.pdf_metadata = pdf_metadata
            doc.ingestion_metadata = ingestion_metadata
            doc.page_count = pdf_metadata.page_count
            doc.total_chunks = ingestion_metadata.total_chunks
        await self.save_to_disk()

    async def get(self, document_id: str) -> Document | None:
        async with self._lock:
            return self._docs.get(document_id)

    async def get_all(self, status: str | None = None) -> list[Document]:
        async with self._lock:
            docs = list(self._docs.values())
        if status:
            docs = [d for d in docs if d.status == status]
        return docs

    async def get_by_user(self, user_id: str, status: str | None = None) -> list[Document]:
        async with self._lock:
            docs = [d for d in self._docs.values() if d.user_id == user_id]
        if status:
            docs = [d for d in docs if d.status == status]
        return docs

    async def delete(self, document_id: str) -> bool:
        async with self._lock:
            removed = self._docs.pop(document_id, None) is not None
        if removed:
            await self.save_to_disk()
        return removed

    async def exists(self, document_id: str) -> bool:
        async with self._lock:
            return document_id in self._docs

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def save_to_disk(self) -> None:
        if not self._persist_path:
            return
        os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
        async with self._lock:
            data = {did: self._doc_to_dict(d) for did, d in self._docs.items()}
        try:
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning("Failed to save registry to disk: %s", exc)

    async def load_from_disk(self) -> None:
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)
            async with self._lock:
                for did, d in data.items():
                    try:
                        self._docs[did] = self._dict_to_doc(d)
                    except Exception:
                        pass
            logger.info("Loaded %d documents from registry on disk", len(data))
        except Exception as exc:
            logger.warning("Failed to load registry from disk: %s", exc)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _doc_to_dict(doc: Document) -> dict:
        return {
            "document_id": doc.document_id,
            "filename": doc.filename,
            "file_path": doc.file_path,
            "file_size_bytes": doc.file_size_bytes,
            "user_id": doc.user_id,
            "status": doc.status,
            "page_count": doc.page_count,
            "total_chunks": doc.total_chunks,
            "created_at": doc.created_at.isoformat(),
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            "error_message": doc.error_message,
            "pdf_metadata": doc.pdf_metadata.model_dump() if doc.pdf_metadata else None,
            "ingestion_metadata": doc.ingestion_metadata.model_dump() if doc.ingestion_metadata else None,
        }

    @staticmethod
    def _dict_to_doc(d: dict) -> Document:
        doc = Document.__new__(Document)
        doc.document_id = d["document_id"]
        doc.filename = d["filename"]
        doc.file_path = d["file_path"]
        doc.file_size_bytes = d["file_size_bytes"]
        doc.user_id = d.get("user_id", "")
        doc.status = d["status"]
        doc.page_count = d.get("page_count", 0)
        doc.total_chunks = d.get("total_chunks", 0)
        doc.created_at = datetime.fromisoformat(d["created_at"])
        doc.processed_at = datetime.fromisoformat(d["processed_at"]) if d.get("processed_at") else None
        doc.error_message = d.get("error_message")
        doc.pdf_metadata = PDFMetadata(**d["pdf_metadata"]) if d.get("pdf_metadata") else None
        doc.ingestion_metadata = IngestionMetadata(**d["ingestion_metadata"]) if d.get("ingestion_metadata") else None
        return doc
