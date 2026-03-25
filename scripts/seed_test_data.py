"""
Test Data Seeding Script
=========================

Purpose:
    Populates the system with sample PDF documents and pre-computed
    embeddings for development and testing. Useful for quickly spinning
    up a populated instance without manually uploading files.

What It Does:
    1. Creates a test session
    2. Uploads sample PDF files from a test_data/ directory (if present)
       or generates minimal synthetic PDFs
    3. Triggers the full ingestion pipeline for each document
    4. Verifies documents are queryable
    5. Prints summary (document count, chunk count, vector count)

Usage:
    python scripts/seed_test_data.py

    Environment:
        Requires OPENAI_API_KEY set (for embedding generation)
        Uses the same config as the main application

Dependencies:
    - httpx (for API calls to the running service)
    - app.config (Settings)
"""
