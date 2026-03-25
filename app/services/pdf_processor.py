"""
PDF Processing Service
=======================

Purpose:
    Extracts raw text from uploaded PDF files. This is the first stage of the
    ingestion pipeline: Upload -> **Parse** -> Clean -> Chunk -> Embed -> Store.

Strategy:
    Dual-parser approach with automatic fallback:

    1. Primary parser: PyMuPDF (fitz)
       - Fastest Python PDF library (~10x faster than pdfplumber)
       - Handles most well-formed PDFs correctly
       - Extracts text, page count, and document metadata

    2. Fallback parser: pdfplumber
       - Superior handling of table-heavy and complex-layout PDFs
       - Activated when PyMuPDF yields < MINIMUM_CHARS_PER_PAGE threshold
         (indicates the PDF may have complex layouts PyMuPDF can't handle)

    3. Quality gate:
       - If both parsers yield insufficient text, mark document as "error"
         with message indicating possible scanned/image-only PDF
       - Future extension point: OCR via Tesseract for scanned PDFs

Inputs:
    file_path: str
        Path to the uploaded PDF file on disk.

    document_id: str
        UUID to associate with the extracted content.

Outputs:
    ParsedDocument:
        A structured result containing:
        - pages: list[PageContent]
            Each PageContent has:
            - page_number: int (1-based)
            - raw_text: str (unprocessed text from this page)
            - char_count: int
        - metadata: dict (title, author, creation_date, producer, page_count)
        - parser_used: str ("pymupdf" | "pdfplumber")
        - total_chars: int

Error Handling:
    - Corrupted PDF: raises PDFParsingError with details
    - Password-protected PDF: raises PDFParsingError("PDF is encrypted")
    - Empty PDF: raises PDFParsingError("PDF contains no extractable text")

Performance:
    - PyMuPDF processes ~100 pages/second on average hardware
    - Fallback adds ~5x latency but only triggers for edge-case PDFs
    - File I/O is the bottleneck; parsing itself is CPU-bound

Dependencies:
    - PyMuPDF (fitz)
    - pdfplumber
    - app.models.document
"""
