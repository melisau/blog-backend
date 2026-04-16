from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, Link, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, TEXT, IndexModel

from models.category import Category


class Blog(Document):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author_id: PydanticObjectId
    # Link[Category] stores a DBRef in MongoDB; use category.$id to query the ObjectId directly.
    category: Optional[Link[Category]] = None
    tags: List[str] = Field(default_factory=list)
    cover_image_url: Optional[str] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    # updated_at is not auto-updated; the router must set it explicitly on every PATCH.
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "blogs"
        indexes = [
            # Compound TEXT index covers both title and content so that
            # $text searches match against either field. A collection can
            # have only one TEXT index, so both fields must be declared together.
            IndexModel([("title", TEXT), ("content", TEXT)], name="blog_text"),
            # Link stores as DBRef, so the filterable ObjectId lives at category.$id, not category.
            IndexModel([("category.$id", ASCENDING)], name="category_id"),
        ]
