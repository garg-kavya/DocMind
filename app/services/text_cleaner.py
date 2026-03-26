"""Text Cleaning Service — normalize raw PDF text."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.pdf_processor import ParsedDocument


class TextCleanerService:
    """Normalize and clean raw text extracted from PDFs."""

    def clean(self, parsed_document: "ParsedDocument") -> tuple[str, list[int]]:
        """Clean all pages and return (cleaned_text, page_boundary_offsets).

        page_boundary_offsets[i] is the char offset in cleaned_text where
        page i+1 begins (0-indexed list, so offset[0] is always 0).
        """
        pages = parsed_document.pages
        if not pages:
            return "", []

        # Detect repeated headers/footers across pages
        header_footer_patterns = self._detect_headers_footers(pages)

        cleaned_pages: list[str] = []
        for page in pages:
            text = page.raw_text
            text = self._normalize_unicode(text)
            text = self._normalize_whitespace(text)
            text = self._rejoin_hyphenated(text)
            text = self._remove_headers_footers(text, header_footer_patterns)
            text = self._remove_control_chars(text)
            text = self._consolidate_blank_lines(text)
            cleaned_pages.append(text)

        # Build boundary offsets (char offset of each page's start in full text)
        page_boundary_offsets: list[int] = []
        joined_parts: list[str] = []
        current_offset = 0
        for page_text in cleaned_pages:
            page_boundary_offsets.append(current_offset)
            joined_parts.append(page_text)
            current_offset += len(page_text) + 1  # +1 for the joining newline

        cleaned_text = "\n".join(joined_parts)
        return cleaned_text, page_boundary_offsets

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalize_unicode(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        replacements = {
            "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "-",
            "\u00a0": " ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        # Collapse multiple spaces (but preserve newlines)
        text = re.sub(r"[ \t]+", " ", text)
        # Remove trailing spaces on each line
        text = re.sub(r" +\n", "\n", text)
        return text

    def _rejoin_hyphenated(self, text: str) -> str:
        # "docu-\nment" → "document" (soft hyphen at line break)
        return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    def _detect_headers_footers(self, pages: object) -> set[str]:
        """Return set of repeated line patterns that appear in >50% of pages."""
        from app.services.pdf_processor import PageContent

        all_pages: list[PageContent] = pages  # type: ignore[assignment]
        if len(all_pages) < 3:
            return set()

        line_counter: Counter = Counter()
        for page in all_pages:
            lines = page.raw_text.splitlines()
            # Check first 2 and last 2 lines
            candidates = lines[:2] + lines[-2:]
            for line in candidates:
                stripped = line.strip()
                if stripped and len(stripped) < 120:
                    line_counter[stripped] += 1

        threshold = max(2, len(all_pages) * 0.5)
        return {line for line, count in line_counter.items() if count >= threshold}

    def _remove_headers_footers(self, text: str, patterns: set[str]) -> str:
        if not patterns:
            return text
        lines = text.splitlines()
        cleaned = [line for line in lines if line.strip() not in patterns]
        return "\n".join(cleaned)

    def _remove_control_chars(self, text: str) -> str:
        # Remove control chars except \n and \t
        return re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

    def _consolidate_blank_lines(self, text: str) -> str:
        # Reduce 3+ consecutive blank lines to 2
        return re.sub(r"\n{3,}", "\n\n", text)
