"""
PDF Processor Tests
====================

Purpose:
    Tests for the PDF parsing and text extraction service.

Test Cases:

    test_parse_valid_pdf:
        Given a well-formed PDF, assert that:
        - All pages are extracted
        - Text content is non-empty
        - Page numbers are correct (1-based)
        - Metadata is populated

    test_parse_multi_page_pdf:
        Given a multi-page PDF, assert page count matches.

    test_parse_encrypted_pdf:
        Given a password-protected PDF, assert PDFParsingError is raised.

    test_parse_corrupted_file:
        Given a non-PDF file (e.g., JPEG renamed to .pdf), assert error.

    test_parse_empty_pdf:
        Given a PDF with no extractable text (scanned image-only),
        assert appropriate error or fallback behavior.

    test_fallback_to_pdfplumber:
        Given a PDF where PyMuPDF extracts minimal text, assert that
        pdfplumber fallback is triggered and produces better output.

    test_metadata_extraction:
        Assert title, author, and creation_date are extracted when present.

Dependencies:
    - pytest
    - app.services.pdf_processor
"""
