"""File I/O utilities for PDF upload handling."""
from __future__ import annotations

import os
import uuid

import aiofiles
from fastapi import UploadFile

from app.exceptions import FileTooLargeError, InvalidFileTypeError

_PDF_MAGIC = b"%PDF"


async def save_upload(
    upload_file: UploadFile,
    upload_dir: str,
    max_size_mb: int = 50,
) -> tuple[str, str]:
    """Save an uploaded file to disk.

    Returns (file_path, document_id).
    """
    ensure_directory(upload_dir)
    document_id = str(uuid.uuid4())
    safe_name = os.path.basename(upload_file.filename or "upload.pdf")
    file_path = os.path.join(upload_dir, f"{document_id}_{safe_name}")

    content = await upload_file.read()
    if not content:
        raise InvalidFileTypeError("Uploaded file is empty.")

    max_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise FileTooLargeError(
            f"File size {len(content) // (1024*1024)}MB exceeds limit of {max_size_mb}MB."
        )

    if not content.startswith(_PDF_MAGIC):
        raise InvalidFileTypeError("Uploaded file is not a valid PDF.")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return file_path, document_id


def validate_pdf(file_path: str) -> bool:
    """Return True if the file at *file_path* looks like a valid PDF."""
    try:
        with open(file_path, "rb") as f:
            return f.read(4) == _PDF_MAGIC
    except OSError:
        return False


def cleanup_file(file_path: str) -> None:
    """Remove a file from disk, ignoring errors if it doesn't exist."""
    try:
        os.remove(file_path)
    except OSError:
        pass


def ensure_directory(path: str) -> None:
    """Create directory (and parents) if it does not exist."""
    os.makedirs(path, exist_ok=True)
