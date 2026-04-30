from datetime import datetime, timezone

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class FollowEvent(Document):
    follower_id: PydanticObjectId
    following_id: PydanticObjectId
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Settings:
        name = "follow_events"
        indexes = [
            IndexModel(
                [("follower_id", ASCENDING), ("following_id", ASCENDING)],
                name="follower_following_unique",
                unique=True,
            ),
            IndexModel([("following_id", ASCENDING), ("created_at", ASCENDING)], name="following_created_at"),
        ]
