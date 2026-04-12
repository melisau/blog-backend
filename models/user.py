from datetime import datetime, timezone

from beanie import Document
from pydantic import EmailStr, Field
from pymongo import ASCENDING, IndexModel


class User(Document):
    username: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    hashed_password: str = Field(..., min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("username", ASCENDING)], name="username_unique", unique=True),
            IndexModel([("email", ASCENDING)], name="email_unique", unique=True),
        ]
