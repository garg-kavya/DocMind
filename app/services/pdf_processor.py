"""PDF Processing Service — parse PDF to structured text."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.exceptions import PDFParsingError
from app.schemas.metadata import PDFMetadata
from app.utils.logging import get_logger

logger = get_logger(__name__)

MINIMUM_CHARS_PER_PAGE = 50  # below this, try pdfplumber fallback


@dataclass
class PageContent:
    page_number: int  # 1-based
    raw_text: str
    char_count: int


@dataclass
class ParsedDocument:
    document_id: str
    pages: list[PageContent]
    pdf_metadata: PDFMetadata
    parser_used: str
    total_chars: int = field(init=False)

    def __post_init__(self) -> None:
        self.total_chars = sum(p.char_count for p in self.pages)


class PDFProcessorService:
    """Parse a PDF file into structured per-page text."""

    def parse(self, file_path: str, document_id: str) -> ParsedDocument:
        """Primary entry point. Tries PyMuPDF, falls back to pdfplumber."""
        if not os.path.exists(file_path):
            raise PDFParsingError(f"File not found: {file_path}")

        try:
            result = self._parse_pymupdf(file_path, document_id)
        except Exception as exc:
            raise PDFParsingError(f"PyMuPDF failed: {exc}", detail=str(exc)) from exc

        avg_chars = result.total_chars / max(len(result.pages), 1)
        if avg_chars < MINIMUM_CHARS_PER_PAGE:
            logger.info(
                "PyMuPDF yielded low char count (%.1f/page); trying pdfplumber",
                avg_chars,
                extra={"document_id": document_id},
            )
            try:
                result = self._parse_pdfplumber(file_path, document_id)
            except Exception as exc:
                logger.warning("pdfplumber fallback also failed: %s", exc)

        if result.total_chars < MINIMUM_CHARS_PER_PAGE:
            raise PDFParsingError(
                "PDF contains no extractable text. It may be scanned/image-only.",
                detail=f"Total chars: {result.total_chars}",
            )

        logger.info(
            "Parsed %d pages, %d chars using %s",
            len(result.pages),
            result.total_chars,
            result.parser_used,
            extra={"document_id": document_id},
        )
        return result

    # ------------------------------------------------------------------
    # Private parsers
    # ------------------------------------------------------------------

    def _parse_pymupdf(self, file_path: str, document_id: str) -> ParsedDocument:
        import fitz  # PyMuPDF

        pages: list[PageContent] = []
        meta: dict = {}

        with fitz.open(file_path) as doc:
            if doc.is_encrypted:
                raise PDFParsingError("PDF is password-protected / encrypted.")

            raw_meta = doc.metadata or {}
            meta = {
                "title": raw_meta.get("title"),
                "author": raw_meta.get("author"),
                "creation_date": raw_meta.get("creationDate"),
                "producer": raw_meta.get("producer"),
            }

            for i, page in enumerate(doc):
                text = page.get_text("text")
                pages.append(PageContent(
                    page_number=i + 1,
                    raw_text=text,
                    char_count=len(text),
                ))

        pdf_metadata = PDFMetadata(
            title=meta.get("title"),
            author=meta.get("author"),
            creation_date=meta.get("creation_date"),
            producer=meta.get("producer"),
            page_count=len(pages),
            file_size_bytes=os.path.getsize(file_path),
            parser_used="pymupdf",
        )
        return ParsedDocument(
            document_id=document_id,
            pages=pages,
            pdf_metadata=pdf_metadata,
            parser_used="pymupdf",
        )

    def _parse_pdfplumber(self, file_path: str, document_id: str) -> ParsedDocument:
        import pdfplumber

        pages: list[PageContent] = []

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages.append(PageContent(
                    page_number=i + 1,
                    raw_text=text,
                    char_count=len(text),
                ))

        pdf_metadata = PDFMetadata(
            page_count=len(pages),
            file_size_bytes=os.path.getsize(file_path),
            parser_used="pdfplumber",
        )
        return ParsedDocument(
            document_id=document_id,
            pages=pages,
            pdf_metadata=pdf_metadata,
            parser_used="pdfplumber",
        )
