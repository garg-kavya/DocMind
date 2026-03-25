"""
File Utility Functions
=======================

Purpose:
    File I/O operations for PDF upload handling, temp file management,
    and cleanup.

Functions:

    save_upload(upload_file: UploadFile, upload_dir: str) -> tuple[str, str]:
        Saves an uploaded file to disk with a unique name.
        Inputs:
            upload_file: FastAPI UploadFile object
            upload_dir: directory to save to
        Outputs:
            (file_path, document_id) — path on disk and generated UUID
        Behavior:
            - Generates UUID for document_id
            - Saves as {upload_dir}/{document_id}_{original_filename}
            - Validates file is non-empty
            - Returns path and ID

    validate_pdf(file_path: str) -> bool:
        Checks that a file is a valid PDF.
        Inputs: path to file
        Outputs: True if valid PDF, False otherwise
        Checks:
            - File starts with %PDF magic bytes
            - File is not empty
            - File size is within MAX_UPLOAD_SIZE_MB

    cleanup_file(file_path: str) -> None:
        Removes a file from disk (used for cleanup after processing errors).

    ensure_directory(path: str) -> None:
        Creates a directory if it doesn't exist.

Dependencies:
    - os, shutil (stdlib)
    - uuid (stdlib)
    - aiofiles (async file I/O)
    - fastapi (UploadFile)
"""
