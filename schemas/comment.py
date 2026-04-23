from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.types import PyObjectId


class CommentCreate(BaseModel):
    # blog_id is taken from the URL path parameter, not the request body.
    content: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    class CommentAuthorResponse(BaseModel):
        id: PyObjectId
        username: str
        icon_id: int | None = None

    id: PyObjectId
    blog_id: PyObjectId
    author_id: PyObjectId
    author: Optional[CommentAuthorResponse] = None
    content: str
    created_at: datetime
