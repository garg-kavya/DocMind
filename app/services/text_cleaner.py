"""
Text Cleaning Service
======================

Purpose:
    Normalizes and cleans raw text extracted from PDFs. This is the second
    stage of the ingestion pipeline: Upload -> Parse -> **Clean** -> Chunk -> Embed -> Store.

    PDF-extracted text often contains artifacts that degrade embedding quality
    and retrieval precision. This service addresses those artifacts.

Cleaning Operations (applied in order):

    1. Unicode Normalization
       - Apply NFKC normalization to standardize character representations
       - Replace common Unicode artifacts (smart quotes, em-dashes, etc.)

    2. Whitespace Normalization
       - Collapse multiple consecutive spaces into single spaces
       - Normalize various whitespace characters (tabs, non-breaking spaces)
       - Preserve paragraph breaks (double newlines) as semantic boundaries

    3. Hyphenated Line-Break Rejoining
       - Detect words split across lines by hyphens (e.g., "docu-\\nment")
       - Rejoin into "document" while preserving legitimate hyphens
         (e.g., "state-of-the-art" stays unchanged)
       - Heuristic: rejoin if the combined word exists in a word frequency
         list or if both fragments are < 3 chars

    4. Header/Footer Removal
       - Detect repeated text appearing at the top/bottom of multiple pages
       - Remove page numbers, running headers, and running footers
       - Heuristic: if the same text (±whitespace) appears in the first/last
         N lines of >50% of pages, classify it as header/footer

    5. Special Character Handling
       - Remove control characters (except newlines)
       - Strip excessive punctuation artifacts from OCR
       - Preserve mathematical symbols and common special characters

    6. Empty Line Consolidation
       - Reduce 3+ consecutive empty lines to 2 (paragraph boundary)

Inputs:
    raw_text: str
        Raw text for a single page or full document.

    pages: list[PageContent] (optional)
        If provided, enables cross-page header/footer detection.

Outputs:
    cleaned_text: str
        Normalized text ready for chunking.

Dependencies:
    - unicodedata (stdlib)
    - re (stdlib)
"""
