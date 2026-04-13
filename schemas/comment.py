from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.types import PyObjectId


class CommentCreate(BaseModel):
    # blog_id is taken from the URL path parameter, not the request body.
    content: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    blog_id: PyObjectId
    author_id: PyObjectId
    content: str
    created_at: datetime
