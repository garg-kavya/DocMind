"""
Performance Benchmarking Script
==================================

Purpose:
    Measures end-to-end latency and retrieval quality metrics for the
    RAG pipeline. Used to validate performance targets and tune parameters.

Benchmarks:

    1. Ingestion Latency
       - Measures time for: parse + clean + chunk + embed + store
       - Broken down by stage
       - Tested with PDFs of varying sizes (1, 10, 50, 100 pages)

    2. Query Latency (E2E)
       - Measures total time from query submission to complete response
       - Breakdown: reformulation + embedding + retrieval + generation
       - Target: median < 2 seconds

    3. Time to First Token (Streaming)
       - Measures time from query submission to first SSE token event
       - Target: < 1.2 seconds

    4. Retrieval Quality
       - Precision@k: fraction of top-k chunks that are relevant
       - Tested with predefined question-answer pairs
       - Measures across different chunk_size and top_k combinations:
         * chunk_size: [256, 384, 512, 768, 1024]
         * top_k: [3, 5, 7, 10]

    5. Throughput
       - Concurrent query load test (10, 25, 50 concurrent users)
       - Measures p50, p95, p99 latencies

Output:
    - Console table with results
    - JSON file with detailed metrics (benchmark_results.json)

Usage:
    python scripts/benchmark.py --queries 50 --concurrent 10

Dependencies:
    - httpx (AsyncClient)
    - asyncio
    - time
    - json
    - argparse
"""
