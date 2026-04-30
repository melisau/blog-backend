from datetime import datetime, timezone

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class Favorite(Document):
    user_id: PydanticObjectId
    blog_id: PydanticObjectId
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "favorites"
        indexes = [
            IndexModel(
                [("user_id", ASCENDING), ("blog_id", ASCENDING)],
                name="user_blog_unique",
                unique=True,
            ),
            IndexModel([("blog_id", ASCENDING)], name="blog_id"),
        ]
