"""User domain model."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    email: str
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    hashed_password: str | None = None       # None for OAuth-only users
    google_id: str | None = None
    auth_provider: str = "email"             # "email" | "google"
    name: str | None = None
