"""In-memory LRU cache backend."""
from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Any

from app.cache.cache_backend import CacheBackend


class InMemoryCache(CacheBackend):

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600) -> None:
        self._store: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry["expires_at"] is not None and time.monotonic() > entry["expires_at"]:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return entry["value"]

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.monotonic() + ttl if ttl > 0 else None
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            elif len(self._store) >= self._max_size:
                self._store.popitem(last=False)  # evict LRU
            self._store[key] = {"value": value, "expires_at": expires_at}
            self._sets += 1

    async def delete(self, key: str) -> None:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                self._deletes += 1

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def stats(self) -> dict:
        async with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "sets": self._sets,
                "deletes": self._deletes,
                "current_size": len(self._store),
            }
