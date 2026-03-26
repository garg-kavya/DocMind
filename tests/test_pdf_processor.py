"""Tests for PDFProcessorService — parsing and text extraction."""
from __future__ import annotations

import pytest

from app.exceptions import PDFParsingError
from app.services.pdf_processor import PDFProcessorService


@pytest.fixture
def processor() -> PDFProcessorService:
    return PDFProcessorService()


# ---------------------------------------------------------------------------
# Valid PDF
# ---------------------------------------------------------------------------

def test_parse_valid_pdf(processor, sample_pdf_file):
    result = processor.parse(sample_pdf_file, "doc-001")

    assert result.document_id == "doc-001"
    assert len(result.pages) >= 1
    assert result.total_chars > 0
    assert result.pdf_metadata.page_count == len(result.pages)
    assert result.pdf_metadata.file_size_bytes > 0
    assert result.parser_used in ("pymupdf", "pdfplumber")


def test_parse_returns_1based_page_numbers(processor, sample_pdf_file):
    result = processor.parse(sample_pdf_file, "doc-002")
    for i, page in enumerate(result.pages):
        assert page.page_number == i + 1


def test_parse_text_non_empty(processor, sample_pdf_file):
    result = processor.parse(sample_pdf_file, "doc-003")
    total = sum(p.char_count for p in result.pages)
    assert total > 0


def test_parse_metadata_populated(processor, sample_pdf_file):
    result = processor.parse(sample_pdf_file, "doc-004")
    meta = result.pdf_metadata
    assert meta.page_count > 0
    assert meta.file_size_bytes > 0
    assert meta.parser_used in ("pymupdf", "pdfplumber")


# ---------------------------------------------------------------------------
# File not found / corrupt
# ---------------------------------------------------------------------------

def test_parse_missing_file_raises(processor):
    with pytest.raises(PDFParsingError):
        processor.parse("/nonexistent/path/file.pdf", "doc-bad")


def test_parse_non_pdf_bytes_raises(processor, tmp_path):
    bad_file = tmp_path / "not_a_pdf.pdf"
    bad_file.write_bytes(b"\xff\xd8\xff\xe0JFIF")  # JPEG magic bytes
    with pytest.raises(PDFParsingError):
        processor.parse(str(bad_file), "doc-corrupt")


def test_parse_empty_file_raises(processor, tmp_path):
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")
    with pytest.raises(PDFParsingError):
        processor.parse(str(empty_file), "doc-empty")


# ---------------------------------------------------------------------------
# Multi-page PDF (build programmatically)
# ---------------------------------------------------------------------------

def _make_multi_page_pdf(n_pages: int) -> bytes:
    """Build a minimal valid PDF with n_pages pages containing text."""
    streams = []
    page_objects = []
    for i in range(n_pages):
        text = f"(Page {i + 1} content for testing purposes.)"
        s = f"BT /F1 12 Tf 100 {700 - i * 20} Td {text} Tj ET".encode()
        streams.append(s)

    # Very minimal cross-reference / offset tracking not needed for
    # functional tests — PyMuPDF is tolerant. Use a single-stream approach.
    content = b"BT /F1 12 Tf"
    for i in range(n_pages):
        content += (
            f" 100 {700 - i * 30} Td "
            f"(Page {i+1} contains sample text for extraction testing purposes.) Tj"
        ).encode()
    content += b" ET"

    length = len(content)
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(length).encode() + b" >>\nstream\n"
        + content + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000274 00000 n \n"
        b"0000000410 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n480\n%%EOF"
    )
    return pdf


def test_parse_single_page_pdf(processor, tmp_path):
    path = tmp_path / "single.pdf"
    path.write_bytes(_make_multi_page_pdf(1))
    result = processor.parse(str(path), "doc-single")
    assert len(result.pages) == 1


# ---------------------------------------------------------------------------
# ParsedDocument helper
# ---------------------------------------------------------------------------

def test_total_chars_is_sum_of_page_chars(processor, sample_pdf_file):
    result = processor.parse(sample_pdf_file, "doc-chars")
    expected = sum(p.char_count for p in result.pages)
    assert result.total_chars == expected


def test_page_char_count_matches_text_length(processor, sample_pdf_file):
    result = processor.parse(sample_pdf_file, "doc-len")
    for page in result.pages:
        assert page.char_count == len(page.raw_text)
