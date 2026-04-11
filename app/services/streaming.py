"""SSE Streaming Handler — wraps async token generator into StreamingResponse."""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi.responses import StreamingResponse

from app.models.query import StreamingChunk


class StreamingHandler:

    @staticmethod
    def create_stream_response(
        token_generator: AsyncGenerator[StreamingChunk, None],
        query_id: str | None = None,
    ) -> StreamingResponse:
        """Wrap an async generator of StreamingChunk into a FastAPI SSE response.

        query_id is omitted from headers — it is emitted in the 'done' SSE event body
        where it is available after the pipeline has assigned it.
        """

        async def event_stream() -> AsyncGenerator[str, None]:
            async for chunk in token_generator:
                yield StreamingHandler.format_sse_event(chunk.event, chunk.data)

        headers: dict[str, str] = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        if query_id is not None:
            headers["X-Query-Id"] = query_id

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers=headers,
        )

    @staticmethod
    def format_sse_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
