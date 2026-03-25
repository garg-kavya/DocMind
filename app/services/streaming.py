"""
Streaming Response Handler
============================

Purpose:
    Manages Server-Sent Events (SSE) streaming for low-latency token-by-token
    response delivery. Enables the client to begin displaying the answer
    as soon as the first token is generated, rather than waiting for the
    complete response.

Streaming Architecture:

    1. Pre-stream phase (non-streamed, blocking):
       - Query reformulation (~200-400ms)
       - Query embedding (~100-150ms)
       - Vector search + re-ranking (~50-150ms)
       Total pre-stream: ~350-700ms

    2. Stream phase (SSE):
       - LLM generates tokens with stream=True
       - Each token is wrapped in an SSE event and sent immediately
       - Time to first token: ~300-500ms after retrieval
       - Total time to first visible token: ~650-1200ms (well under 2s target)

    3. Post-stream phase:
       - Final "done" event with complete citations and metadata
       - Session history updated with complete response

SSE Event Format:
    event: token
    data: {"text": "The", "query_id": "abc-123"}

    event: token
    data: {"text": " revenue", "query_id": "abc-123"}

    event: citation
    data: {"citations": [...], "query_id": "abc-123"}

    event: done
    data: {"query_id": "abc-123", "total_tokens": 142, "retrieval_time_ms": 87}

    event: error
    data: {"message": "Generation failed", "query_id": "abc-123"}

Methods:

    create_stream_response(
        query: QueryContext,
        context: RetrievedContext,
        generator: GeneratorService
    ) -> StreamingResponse:
        Creates a FastAPI StreamingResponse that yields SSE events.
        Inputs:
            query: the enriched query context
            context: retrieved chunks
            generator: the generation service (used in streaming mode)
        Outputs:
            FastAPI StreamingResponse with media_type="text/event-stream"

    format_sse_event(event_type: str, data: dict) -> str:
        Formats a single SSE event string.
        Inputs: event type name and data payload
        Outputs: formatted "event: {type}\\ndata: {json}\\n\\n" string

Client-Side Consumption:
    The client should use EventSource or fetch with ReadableStream to
    consume the SSE endpoint. Tokens are concatenated client-side to
    build the progressive response.

Error Handling:
    - If the LLM stream errors mid-generation, an "error" event is sent
      and the stream is closed
    - Client disconnection is detected and generation is cancelled to
      avoid wasted API costs

Dependencies:
    - fastapi (StreamingResponse)
    - asyncio
    - json
    - app.services.generator (GeneratorService)
    - app.models.query (QueryContext, RetrievedContext, StreamingChunk)
"""
