"""Performance benchmarking script for the RAG PDF Q&A service."""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000/api/v1"

SAMPLE_QUESTIONS = [
    "What is machine learning?",
    "How does natural language processing work?",
    "What are neural networks used for?",
    "Explain deep learning architectures.",
    "What is transfer learning?",
    "How is accuracy measured in classification?",
    "What is overfitting and how to prevent it?",
    "Describe the transformer architecture.",
    "What is reinforcement learning?",
    "How does gradient descent work?",
]


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def _make_minimal_pdf(page_text: str) -> bytes:
    content = f"BT /F1 12 Tf 100 700 Td ({page_text}) Tj ET".encode()
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
        b"0000000115 00000 n \n0000000274 00000 n \n0000000400 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n470\n%%EOF"
    )


async def upload_document(client: httpx.AsyncClient, session_id: str,
                          pdf_bytes: bytes, name: str) -> str | None:
    try:
        resp = await client.post(
            f"{BASE_URL}/documents/upload",
            files={"file": (name, pdf_bytes, "application/pdf")},
            data={"session_id": session_id},
            timeout=60.0,
        )
        if resp.status_code == 202:
            return resp.json()["document_id"]
    except Exception as exc:
        print(f"  Upload error: {exc}")
    return None


async def create_session(client: httpx.AsyncClient) -> str | None:
    try:
        resp = await client.post(f"{BASE_URL}/sessions", json={}, timeout=10.0)
        if resp.status_code == 201:
            return resp.json()["session_id"]
    except Exception as exc:
        print(f"  Session create error: {exc}")
    return None


async def wait_for_ready(client: httpx.AsyncClient, doc_id: str,
                         max_wait: int = 60) -> bool:
    for _ in range(max_wait):
        try:
            resp = await client.get(f"{BASE_URL}/documents/{doc_id}", timeout=5.0)
            if resp.json().get("status") == "ready":
                return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Benchmark 1: Ingestion latency
# ---------------------------------------------------------------------------

async def benchmark_ingestion(client: httpx.AsyncClient, n_runs: int = 3) -> dict:
    print("\n[1] Ingestion Latency")
    latencies = []

    for i in range(n_runs):
        session_id = await create_session(client)
        if not session_id:
            continue

        pdf = _make_minimal_pdf(f"Benchmark document {i} content for ingestion testing.")
        t0 = time.monotonic()
        doc_id = await upload_document(client, session_id, pdf, f"bench_{i}.pdf")
        if doc_id:
            ready = await wait_for_ready(client, doc_id, max_wait=30)
            elapsed = (time.monotonic() - t0) * 1000
            if ready:
                latencies.append(elapsed)
                print(f"  Run {i+1}: {elapsed:.0f}ms")
            else:
                print(f"  Run {i+1}: timed out waiting for ready")

    if latencies:
        return {
            "median_ms": round(statistics.median(latencies), 1),
            "mean_ms": round(statistics.mean(latencies), 1),
            "min_ms": round(min(latencies), 1),
            "max_ms": round(max(latencies), 1),
            "n_runs": len(latencies),
        }
    return {"error": "no successful ingestion runs"}


# ---------------------------------------------------------------------------
# Benchmark 2: Query latency (E2E)
# ---------------------------------------------------------------------------

async def benchmark_query_latency(client: httpx.AsyncClient, session_id: str,
                                   document_ids: list[str],
                                   n_queries: int = 10) -> dict:
    print("\n[2] Query Latency (E2E)")
    latencies = []
    questions = (SAMPLE_QUESTIONS * 10)[:n_queries]

    for i, question in enumerate(questions):
        t0 = time.monotonic()
        try:
            resp = await client.post(
                f"{BASE_URL}/query",
                json={
                    "question": question,
                    "session_id": session_id,
                    "document_ids": document_ids,
                },
                timeout=30.0,
            )
            elapsed = (time.monotonic() - t0) * 1000
            if resp.status_code == 200:
                latencies.append(elapsed)
                print(f"  Q{i+1}: {elapsed:.0f}ms")
            else:
                print(f"  Q{i+1}: HTTP {resp.status_code}")
        except Exception as exc:
            print(f"  Q{i+1}: error — {exc}")

    if latencies:
        return {
            "median_ms": round(statistics.median(latencies), 1),
            "mean_ms": round(statistics.mean(latencies), 1),
            "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 1),
            "min_ms": round(min(latencies), 1),
            "max_ms": round(max(latencies), 1),
            "n_queries": len(latencies),
            "target_median_ms": 2000,
            "passed": statistics.median(latencies) < 2000,
        }
    return {"error": "no successful queries"}


# ---------------------------------------------------------------------------
# Benchmark 3: Time to first token (streaming)
# ---------------------------------------------------------------------------

async def benchmark_ttft(client: httpx.AsyncClient, session_id: str,
                          document_ids: list[str], n_runs: int = 5) -> dict:
    print("\n[3] Time to First Token (Streaming)")
    ttfts = []
    questions = (SAMPLE_QUESTIONS * 10)[:n_runs]

    for i, question in enumerate(questions):
        t0 = time.monotonic()
        first_token = None
        try:
            async with client.stream(
                "POST",
                f"{BASE_URL}/query/stream",
                json={
                    "question": question,
                    "session_id": session_id,
                    "document_ids": document_ids,
                },
                timeout=30.0,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data:") and first_token is None:
                        first_token = (time.monotonic() - t0) * 1000
                        break
        except Exception as exc:
            print(f"  Run {i+1}: error — {exc}")
            continue

        if first_token is not None:
            ttfts.append(first_token)
            print(f"  Run {i+1}: {first_token:.0f}ms")

    if ttfts:
        return {
            "median_ttft_ms": round(statistics.median(ttfts), 1),
            "mean_ttft_ms": round(statistics.mean(ttfts), 1),
            "min_ms": round(min(ttfts), 1),
            "max_ms": round(max(ttfts), 1),
            "target_ms": 1200,
            "passed": statistics.median(ttfts) < 1200,
            "n_runs": len(ttfts),
        }
    return {"error": "no successful TTFT measurements"}


# ---------------------------------------------------------------------------
# Benchmark 4: Throughput (concurrent queries)
# ---------------------------------------------------------------------------

async def benchmark_throughput(client: httpx.AsyncClient, session_id: str,
                                document_ids: list[str],
                                concurrency: int = 5,
                                n_queries: int = 10) -> dict:
    print(f"\n[4] Throughput ({concurrency} concurrent users, {n_queries} total queries)")

    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    errors = 0

    async def _query(question: str) -> None:
        nonlocal errors
        async with semaphore:
            t0 = time.monotonic()
            try:
                resp = await client.post(
                    f"{BASE_URL}/query",
                    json={
                        "question": question,
                        "session_id": session_id,
                        "document_ids": document_ids,
                    },
                    timeout=30.0,
                )
                elapsed = (time.monotonic() - t0) * 1000
                if resp.status_code == 200:
                    latencies.append(elapsed)
                else:
                    errors += 1
            except Exception:
                errors += 1

    questions = (SAMPLE_QUESTIONS * 10)[:n_queries]
    t_start = time.monotonic()
    await asyncio.gather(*[_query(q) for q in questions])
    total_elapsed = (time.monotonic() - t_start)

    if latencies:
        sorted_l = sorted(latencies)
        n = len(sorted_l)
        return {
            "concurrency": concurrency,
            "total_queries": n_queries,
            "successful": len(latencies),
            "errors": errors,
            "throughput_qps": round(len(latencies) / total_elapsed, 2),
            "p50_ms": round(sorted_l[int(n * 0.50)], 1),
            "p95_ms": round(sorted_l[int(n * 0.95)], 1),
            "p99_ms": round(sorted_l[min(int(n * 0.99), n - 1)], 1),
            "total_elapsed_s": round(total_elapsed, 2),
        }
    return {"error": "no successful throughput queries", "errors": errors}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _print_table(results: dict) -> None:
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 60)
    for section, data in results.items():
        print(f"\n{section}:")
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"  {k:<30} {v}")
        else:
            print(f"  {data}")
    print("=" * 60)


async def main(args: argparse.Namespace) -> None:
    results: dict = {}

    async with httpx.AsyncClient() as client:
        # Health check
        try:
            health = await client.get(f"{BASE_URL}/health", timeout=5.0)
            if health.status_code != 200:
                print(f"WARNING: service health is {health.json().get('status')}")
        except Exception as exc:
            print(f"ERROR: Cannot reach service at {BASE_URL}: {exc}")
            return

        # Create session and upload benchmark document
        print("\nSetting up benchmark session and document...")
        session_id = await create_session(client)
        if not session_id:
            print("Failed to create benchmark session. Is the server running?")
            return

        pdf = _make_minimal_pdf(
            "Machine learning is a subset of artificial intelligence. "
            "Deep learning uses neural networks. "
            "NLP processes natural language. "
        )
        doc_id = await upload_document(client, session_id, pdf, "benchmark_doc.pdf")
        if not doc_id:
            print("Failed to upload benchmark document.")
            return

        print(f"  Session: {session_id}")
        print(f"  Document: {doc_id}")
        print("  Waiting for ingestion...")
        ready = await wait_for_ready(client, doc_id, max_wait=120)
        if not ready:
            print("  Document did not reach 'ready' status in time.")
        else:
            print("  Document ready.")

        document_ids = [doc_id]

        # Run benchmarks
        if args.ingestion:
            results["ingestion"] = await benchmark_ingestion(client, n_runs=args.runs)

        results["query_latency"] = await benchmark_query_latency(
            client, session_id, document_ids, n_queries=args.queries
        )

        if args.streaming:
            results["ttft"] = await benchmark_ttft(
                client, session_id, document_ids, n_runs=min(5, args.queries)
            )

        if args.concurrent > 1:
            results["throughput"] = await benchmark_throughput(
                client, session_id, document_ids,
                concurrency=args.concurrent,
                n_queries=args.queries,
            )

    _print_table(results)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark the RAG PDF Q&A service.")
    parser.add_argument("--queries", type=int, default=10,
                        help="Number of queries to run (default: 10)")
    parser.add_argument("--concurrent", type=int, default=1,
                        help="Concurrency level for throughput test (default: 1)")
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of ingestion runs (default: 3)")
    parser.add_argument("--output", default="benchmark_results.json",
                        help="Output JSON file path (default: benchmark_results.json)")
    parser.add_argument("--ingestion", action="store_true",
                        help="Include ingestion benchmark (slower)")
    parser.add_argument("--streaming", action="store_true",
                        help="Include TTFT streaming benchmark")
    args = parser.parse_args()

    asyncio.run(main(args))
