"""Shared AsyncOpenAI client factory.

Routes all traffic through Helicone when HELICONE_API_KEY is set, giving
a live dashboard of token usage, costs, latency, and error rates across
every call — completions, embeddings, reformulation, and compression.

Without a key the client connects directly to OpenAI with no overhead.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from app.config import Settings


def make_openai_client(settings: Settings) -> AsyncOpenAI:
    """Return an AsyncOpenAI client, optionally proxied through Helicone."""
    if settings.helicone_api_key:
        return AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url="https://oai.helicone.ai/v1",
            default_headers={
                "Helicone-Auth": f"Bearer {settings.helicone_api_key}",
                "Helicone-Property-App": "DocMind",
            },
        )
    return AsyncOpenAI(api_key=settings.openai_api_key)
