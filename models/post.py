from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, Link, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, TEXT, IndexModel

from models.category import Category


class Post(Document):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author_id: PydanticObjectId
    category: Optional[Link[Category]] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "posts"
        indexes = [
            # Full-text search on title
            IndexModel([("title", TEXT)], name="title_text"),
            # Equality / range filter on category reference
            IndexModel([("category.$id", ASCENDING)], name="category_id"),
        ]
