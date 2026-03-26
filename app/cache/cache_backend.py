"""Abstract cache backend interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Return cached value or None on miss."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store value. Never raises."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove key. No-op if missing."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """True if key exists and has not expired."""

    @abstractmethod
    async def clear(self) -> None:
        """Remove all entries."""

    @abstractmethod
    async def stats(self) -> dict:
        """Return diagnostic counters."""
