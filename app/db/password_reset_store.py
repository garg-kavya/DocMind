"""PostgreSQL-backed password reset token store."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg

from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOKEN_BYTES = 32          # 256-bit token → 64 hex chars
_EXPIRY_MINUTES = 60       # tokens valid for 1 hour


class PasswordResetStore:

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_table(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token      TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    used       BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
        logger.info("Password reset store ready (PostgreSQL)")

    async def create_token(self, user_id: str) -> str:
        """Generate, persist, and return a new reset token for *user_id*."""
        token = secrets.token_hex(_TOKEN_BYTES)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_EXPIRY_MINUTES)
        async with self._pool.acquire() as conn:
            # Invalidate any previous unused token for this user
            await conn.execute(
                "UPDATE password_reset_tokens SET used = TRUE WHERE user_id = $1 AND used = FALSE",
                user_id,
            )
            await conn.execute(
                "INSERT INTO password_reset_tokens (token, user_id, expires_at) VALUES ($1, $2, $3)",
                token, user_id, expires_at,
            )
        return token

    async def consume_token(self, token: str) -> str | None:
        """Validate *token*, mark it as used, and return its user_id.

        Returns None if the token is missing, already used, or expired.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id, expires_at, used FROM password_reset_tokens WHERE token = $1",
                token,
            )
            if row is None or row["used"]:
                return None
            if row["expires_at"] < datetime.now(timezone.utc):
                return None
            await conn.execute(
                "UPDATE password_reset_tokens SET used = TRUE WHERE token = $1", token
            )
            return row["user_id"]

    async def cleanup_expired(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM password_reset_tokens WHERE expires_at < NOW()"
            )
