"""PostgreSQL-backed user store via asyncpg connection pool."""
from __future__ import annotations

import asyncpg

from app.models.user import User
from app.utils.logging import get_logger

logger = get_logger(__name__)

_SELECT = "user_id, email, hashed_password, google_id, auth_provider, name, created_at"


class UserStore:

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_table(self) -> None:
        async with self._pool.acquire() as conn:
            # Full schema for fresh installs
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       TEXT PRIMARY KEY,
                    email         TEXT UNIQUE NOT NULL,
                    hashed_password TEXT,
                    google_id     TEXT UNIQUE,
                    auth_provider TEXT NOT NULL DEFAULT 'email',
                    name          TEXT,
                    created_at    TIMESTAMPTZ NOT NULL
                )
            """)
            # Idempotent migrations for existing installs
            for stmt in [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider TEXT NOT NULL DEFAULT 'email'",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT",
                "ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL",
            ]:
                try:
                    await conn.execute(stmt)
                except Exception:
                    pass  # column already exists or constraint already removed
        logger.info("User store ready (PostgreSQL)")

    # ------------------------------------------------------------------
    # Email / password auth
    # ------------------------------------------------------------------

    async def create_user(self, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id, email, hashed_password, auth_provider, created_at) "
                "VALUES ($1, $2, $3, 'email', $4)",
                user.user_id, user.email, user.hashed_password, user.created_at,
            )
        return user

    async def update_password(self, user_id: str, hashed_password: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET hashed_password = $1 WHERE user_id = $2",
                hashed_password, user_id,
            )

    # ------------------------------------------------------------------
    # Google OAuth
    # ------------------------------------------------------------------

    async def get_by_google_id(self, google_id: str) -> User | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_SELECT} FROM users WHERE google_id = $1", google_id
            )
        return _row_to_user(row)

    async def create_google_user(self, email: str, google_id: str, name: str | None) -> User:
        user = User(email=email, google_id=google_id, auth_provider="google", name=name)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id, email, google_id, auth_provider, name, created_at) "
                "VALUES ($1, $2, $3, 'google', $4, $5)",
                user.user_id, user.email, user.google_id, user.name, user.created_at,
            )
        return user

    async def link_google_id(self, user_id: str, google_id: str, name: str | None) -> None:
        """Attach a Google ID to an existing email/password account."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET google_id = $1, name = COALESCE(name, $2) WHERE user_id = $3",
                google_id, name, user_id,
            )

    # ------------------------------------------------------------------
    # Generic lookups
    # ------------------------------------------------------------------

    async def get_by_email(self, email: str) -> User | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_SELECT} FROM users WHERE email = $1", email
            )
        return _row_to_user(row)

    async def get_by_id(self, user_id: str) -> User | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_SELECT} FROM users WHERE user_id = $1", user_id
            )
        return _row_to_user(row)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_user(row: asyncpg.Record | None) -> User | None:
    if row is None:
        return None
    return User(
        user_id=row["user_id"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        google_id=row["google_id"],
        auth_provider=row["auth_provider"],
        name=row["name"],
        created_at=row["created_at"],
    )
