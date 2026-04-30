from datetime import datetime, timezone
from typing import List

from beanie import Document, PydanticObjectId
from pydantic import EmailStr, Field
from pymongo import ASCENDING, IndexModel


class User(Document):
    username: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    hashed_password: str = Field(..., min_length=1)
    bio: str | None = Field(default=None, max_length=300)
    icon_id: int = Field(default=1, ge=1)
    # Computed engagement counters
    followers_count: int = Field(default=0, ge=0)
    following_count: int = Field(default=0, ge=0)
    # Used to compute unread notification counts from derived events.
    notifications_last_read_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "users"
        # unique=True at the DB level is the last line of defense against race conditions
        # when two concurrent requests pass the application-level duplicate check simultaneously.
        indexes = [
            IndexModel([("username", ASCENDING)], name="username_unique", unique=True),
            IndexModel([("email", ASCENDING)], name="email_unique", unique=True),
        ]
