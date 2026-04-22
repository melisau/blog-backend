from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from schemas.types import PyObjectId


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: Literal["comment", "follow"]
    message: str
    created_at: datetime
    blog_id: Optional[PyObjectId] = None
    actor_user_id: Optional[PyObjectId] = None


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int

