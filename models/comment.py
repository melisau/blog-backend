from datetime import datetime, timezone

from beanie import Document, PydanticObjectId
from pydantic import Field


class Comment(Document):
    post_id: PydanticObjectId
    author_id: PydanticObjectId
    content: str = Field(..., min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "comments"
