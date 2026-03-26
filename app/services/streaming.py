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
        query_id: str,
    ) -> StreamingResponse:
        """Wrap an async generator of StreamingChunk into a FastAPI SSE response."""

        async def event_stream() -> AsyncGenerator[str, None]:
            async for chunk in token_generator:
                yield StreamingHandler.format_sse_event(chunk.event, chunk.data)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Query-Id": query_id,
            },
        )

    @staticmethod
    def format_sse_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
