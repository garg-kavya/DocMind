"""Seed the RAG system with sample documents for development and testing."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000/api/v1"

# ---------------------------------------------------------------------------
# Sample document content
# ---------------------------------------------------------------------------

SAMPLE_DOCUMENTS = [
    {
        "name": "machine_learning_intro.pdf",
        "text": (
            "Machine Learning Introduction\n\n"
            "Machine learning is a branch of artificial intelligence that enables "
            "systems to learn from data without being explicitly programmed. "
            "Algorithms improve through experience and exposure to training data.\n\n"
            "Types of Machine Learning:\n"
            "Supervised learning uses labelled examples to learn input-output mappings. "
            "Unsupervised learning discovers hidden patterns in unlabelled data. "
            "Reinforcement learning trains agents through reward and penalty signals.\n\n"
            "Applications include image recognition, natural language processing, "
            "recommendation systems, fraud detection, and autonomous vehicles. "
            "Key algorithms include linear regression, decision trees, random forests, "
            "support vector machines, and neural networks."
        ),
    },
    {
        "name": "deep_learning_guide.pdf",
        "text": (
            "Deep Learning Guide\n\n"
            "Deep learning is a subset of machine learning that uses artificial neural "
            "networks with multiple layers. Each layer learns progressively more abstract "
            "representations of the input data.\n\n"
            "Key Architectures:\n"
            "Convolutional Neural Networks (CNNs) excel at image and spatial data. "
            "Recurrent Neural Networks (RNNs) handle sequential data like text. "
            "Transformers use attention mechanisms and dominate NLP tasks.\n\n"
            "Training deep networks requires large datasets, significant compute, "
            "and careful hyperparameter tuning. Techniques like batch normalisation, "
            "dropout, and residual connections improve training stability."
        ),
    },
    {
        "name": "nlp_fundamentals.pdf",
        "text": (
            "Natural Language Processing Fundamentals\n\n"
            "NLP is the field of AI focused on enabling computers to understand, "
            "interpret, and generate human language.\n\n"
            "Core Tasks:\n"
            "Tokenisation splits text into words or subword units. "
            "Named entity recognition identifies people, places, and organisations. "
            "Sentiment analysis classifies text as positive, negative, or neutral. "
            "Machine translation converts text from one language to another.\n\n"
            "Modern NLP is dominated by transformer models such as BERT, GPT, and T5. "
            "These are pre-trained on large corpora and fine-tuned for specific tasks. "
            "Word embeddings like Word2Vec and GloVe represent words as dense vectors."
        ),
    },
]


def _make_pdf(text: str) -> bytes:
    """Build a minimal PDF file containing the given text."""
    # Escape parentheses for PDF content stream
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    # Split into 60-char lines for readability in the stream
    words = safe.split()
    lines, line = [], []
    for word in words:
        line.append(word)
        if len(" ".join(line)) > 60:
            lines.append(" ".join(line))
            line = []
    if line:
        lines.append(" ".join(line))

    # Build content stream with multiple Td moves
    stream_parts = ["BT", "/F1 10 Tf", "50 750 Td"]
    for i, ln in enumerate(lines[:80]):  # cap at 80 lines
        if i > 0:
            stream_parts.append("0 -14 Td")
        stream_parts.append(f"({ln}) Tj")
    stream_parts.append("ET")
    content = "\n".join(stream_parts).encode("latin-1", errors="replace")
    length = len(content)

    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(length).encode() + b" >>\nstream\n"
        + content + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000274 00000 n \n0000000410 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n480\n%%EOF"
    )


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

async def health_check(client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
        data = resp.json()
        status = data.get("status", "unknown")
        print(f"  Service health: {status}")
        return resp.status_code in (200, 503)
    except Exception as exc:
        print(f"  Cannot reach service: {exc}")
        return False


async def create_session(client: httpx.AsyncClient) -> str | None:
    resp = await client.post(f"{BASE_URL}/sessions", json={}, timeout=10.0)
    if resp.status_code == 201:
        return resp.json()["session_id"]
    print(f"  Failed to create session: HTTP {resp.status_code}")
    return None


async def upload_pdf(client: httpx.AsyncClient, session_id: str,
                     name: str, pdf_bytes: bytes) -> str | None:
    resp = await client.post(
        f"{BASE_URL}/documents/upload",
        files={"file": (name, pdf_bytes, "application/pdf")},
        data={"session_id": session_id},
        timeout=30.0,
    )
    if resp.status_code == 202:
        doc_id = resp.json()["document_id"]
        print(f"  Uploaded '{name}' -> {doc_id}")
        return doc_id
    print(f"  Upload failed for '{name}': HTTP {resp.status_code} — {resp.text[:200]}")
    return None


async def wait_ready(client: httpx.AsyncClient, doc_id: str,
                     timeout_s: int = 120) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = await client.get(f"{BASE_URL}/documents/{doc_id}", timeout=5.0)
            if resp.status_code == 200:
                status = resp.json().get("status")
                if status == "ready":
                    return True
                if status == "error":
                    msg = resp.json().get("error_message", "unknown error")
                    print(f"  Document {doc_id} ingestion error: {msg}")
                    return False
        except Exception:
            pass
        await asyncio.sleep(2)
    print(f"  Timeout waiting for document {doc_id}")
    return False


async def verify_query(client: httpx.AsyncClient, session_id: str,
                        doc_ids: list[str], question: str) -> bool:
    resp = await client.post(
        f"{BASE_URL}/query",
        json={"question": question, "session_id": session_id,
              "document_ids": doc_ids},
        timeout=60.0,
    )
    if resp.status_code == 200:
        answer = resp.json().get("answer", "")
        confidence = resp.json().get("confidence", 0.0)
        print(f"  Q: {question!r}")
        print(f"  A: {answer[:120]}...")
        print(f"  Confidence: {confidence:.2f}")
        return True
    print(f"  Query failed: HTTP {resp.status_code}")
    return False


# ---------------------------------------------------------------------------
# Main seeding workflow
# ---------------------------------------------------------------------------

async def seed(use_local_pdfs: bool = False, pdf_dir: str = "test_data") -> None:
    print("=" * 60)
    print("RAG PDF Q&A — Test Data Seeding")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        print("\n[1] Health check")
        if not await health_check(client):
            print("Service unavailable. Start the server first:")
            print("  uvicorn app.main:app --reload")
            sys.exit(1)

        print("\n[2] Creating test session")
        session_id = await create_session(client)
        if not session_id:
            sys.exit(1)
        print(f"  Session ID: {session_id}")

        print("\n[3] Uploading documents")
        doc_ids: list[str] = []

        # Try local PDFs first if requested
        if use_local_pdfs:
            pdf_path = Path(pdf_dir)
            local_pdfs = list(pdf_path.glob("*.pdf")) if pdf_path.exists() else []
            if local_pdfs:
                for pdf_file in local_pdfs[:5]:  # cap at 5
                    pdf_bytes = pdf_file.read_bytes()
                    doc_id = await upload_pdf(client, session_id, pdf_file.name, pdf_bytes)
                    if doc_id:
                        doc_ids.append(doc_id)

        # Fall back to synthetic PDFs
        if not doc_ids:
            print("  (Using synthetic PDF documents)")
            for doc_info in SAMPLE_DOCUMENTS:
                pdf_bytes = _make_pdf(doc_info["text"])
                doc_id = await upload_pdf(client, session_id, doc_info["name"], pdf_bytes)
                if doc_id:
                    doc_ids.append(doc_id)

        if not doc_ids:
            print("No documents uploaded successfully.")
            sys.exit(1)

        print(f"\n[4] Waiting for ingestion ({len(doc_ids)} document(s))")
        ready_ids = []
        for doc_id in doc_ids:
            print(f"  Polling {doc_id}...")
            if await wait_ready(client, doc_id):
                ready_ids.append(doc_id)
                print(f"  [OK] {doc_id} ready")
            else:
                print(f"  [FAIL] {doc_id} failed or timed out")

        if not ready_ids:
            print("No documents became ready. Check server logs.")
            sys.exit(1)

        print(f"\n[5] Verifying documents are queryable ({len(ready_ids)} ready)")
        verify_questions = [
            "What is machine learning?",
            "How do neural networks work?",
        ]
        for question in verify_questions:
            await verify_query(client, session_id, ready_ids, question)

        # Fetch final stats
        print("\n[6] Summary")
        list_resp = await client.get(f"{BASE_URL}/documents", timeout=10.0)
        total_docs = list_resp.json().get("total_count", len(ready_ids))
        health_resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
        total_vectors = health_resp.json().get("total_vectors", "N/A")

        print(f"  Session ID      : {session_id}")
        print(f"  Documents ready : {len(ready_ids)}")
        print(f"  Total documents : {total_docs}")
        print(f"  Total vectors   : {total_vectors}")
        print("\nSeeding complete. Use the session ID above to run queries.")
        print(f"  curl -X POST {BASE_URL}/query \\")
        print(f'    -H "Content-Type: application/json" \\')
        print(f'    -d \'{{"question":"What is ML?","session_id":"{session_id}",'
              f'"document_ids":{ready_ids}}}\'')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed the RAG service with test data.")
    parser.add_argument("--local-pdfs", action="store_true",
                        help="Use PDFs from the test_data/ directory if available.")
    parser.add_argument("--pdf-dir", default="test_data",
                        help="Directory containing local test PDFs (default: test_data).")
    args = parser.parse_args()

    asyncio.run(seed(use_local_pdfs=args.local_pdfs, pdf_dir=args.pdf_dir))
