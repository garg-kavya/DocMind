"""Table Extraction Service — extract PDF tables as GFM Markdown chunks."""
from __future__ import annotations

import uuid

from app.models.chunk import Chunk
from app.utils.logging import get_logger
from app.utils.token_counter import count_tokens

logger = get_logger(__name__)


class TableExtractorService:
    """Extract tables from a PDF using pdfplumber and return GFM Markdown Chunks.

    Each table is rendered as a GitHub-Flavored Markdown pipe table.  If a
    table's token count exceeds the budget the data rows are split into
    sub-chunks; the header row is preserved in every sub-chunk so each
    chunk is self-contained and searchable without surrounding context.
    """

    def __init__(self, max_tokens: int = 512) -> None:
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract(
        self,
        file_path: str,
        document_id: str,
        document_name: str,
        start_index: int = 0,
    ) -> list[Chunk]:
        """Extract all tables from *file_path* and return as Chunk objects.

        Tables with no data or only empty cells are skipped.
        pdfplumber errors on individual pages are logged and skipped — the
        pipeline continues with whatever tables could be extracted.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed; skipping table extraction")
            return []

        chunks: list[Chunk] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_num: int = page.page_number  # 1-based
                    try:
                        tables = page.extract_tables() or []
                    except Exception as exc:
                        logger.warning(
                            "Table extraction failed on page %d: %s", page_num, exc
                        )
                        continue

                    for table in tables:
                        table_chunks = self._table_to_chunks(
                            table=table,
                            page_number=page_num,
                            document_id=document_id,
                            document_name=document_name,
                            start_index=start_index + len(chunks),
                        )
                        chunks.extend(table_chunks)

        except Exception as exc:
            logger.warning(
                "pdfplumber could not open %s for table extraction: %s",
                document_name, exc,
            )
            return []

        logger.info(
            "Extracted %d table chunk(s) from %s", len(chunks), document_name
        )
        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _table_to_chunks(
        self,
        table: list[list[str | None]],
        page_number: int,
        document_id: str,
        document_name: str,
        start_index: int,
    ) -> list[Chunk]:
        """Convert one pdfplumber table (list of rows) into Chunk objects."""
        if not table or len(table) < 2:
            return []

        # Normalise: replace None with empty string
        norm: list[list[str]] = [[cell or "" for cell in row] for row in table]

        # Skip fully-empty tables
        if all(cell.strip() == "" for row in norm for cell in row):
            return []

        header = norm[0]
        data_rows = norm[1:]

        result: list[Chunk] = []
        pending: list[list[str]] = []

        for row in data_rows:
            pending.append(row)
            candidate = _rows_to_gfm(header, pending)

            if count_tokens(candidate) > self._max_tokens:
                if len(pending) > 1:
                    # Emit all but the last row, restart with the overflow row
                    emit_text = _rows_to_gfm(header, pending[:-1])
                    result.append(self._make_chunk(
                        emit_text, page_number, document_id, document_name,
                        start_index + len(result),
                    ))
                    pending = [row]
                else:
                    # Single row already over budget — emit it as-is
                    result.append(self._make_chunk(
                        candidate, page_number, document_id, document_name,
                        start_index + len(result),
                    ))
                    pending = []

        if pending:
            emit_text = _rows_to_gfm(header, pending)
            result.append(self._make_chunk(
                emit_text, page_number, document_id, document_name,
                start_index + len(result),
            ))

        return result

    @staticmethod
    def _make_chunk(
        text: str,
        page_number: int,
        document_id: str,
        document_name: str,
        chunk_index: int,
    ) -> Chunk:
        return Chunk(
            document_id=document_id,
            document_name=document_name,
            chunk_index=chunk_index,
            text=text,
            token_count=count_tokens(text),
            page_numbers=[page_number],
            start_char_offset=0,
            end_char_offset=len(text),
            chunk_id=str(uuid.uuid4()),
        )


# ---------------------------------------------------------------------------
# GFM rendering helper
# ---------------------------------------------------------------------------

def _rows_to_gfm(header: list[str], rows: list[list[str]]) -> str:
    """Render *header* + *rows* as a GFM pipe-table string."""

    def _cell(value: str) -> str:
        # Escape pipe characters and collapse internal newlines
        return value.replace("|", "\\|").replace("\n", " ").strip()

    def _row(cells: list[str]) -> str:
        return "| " + " | ".join(_cell(c) for c in cells) + " |"

    separator = "| " + " | ".join("---" for _ in header) + " |"
    lines = [_row(header), separator] + [_row(r) for r in rows]
    return "\n".join(lines)
