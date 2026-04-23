from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.category import CategoryResponse
from schemas.types import PyObjectId


class BlogCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class BlogUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category_id: Optional[str] = None
    tags: Optional[List[str]] = None


class BlogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    class BlogAuthorResponse(BaseModel):
        id: PyObjectId
        username: str
        icon_id: int | None = None

    id: PyObjectId
    title: str
    content: str
    author: BlogAuthorResponse
    category: Optional[CategoryResponse] = None
    tags: List[str]
    cover_image_url: Optional[str] = None
    created_at: datetime
    created_at_display: str
    updated_at: datetime
    # Computed engagement counters (not persisted on the Blog document).
    # Defaulted to 0 so create/update endpoints that don't recompute them
    # still satisfy the response schema.
    favorite_count: int = 0
    comment_count: int = 0


class BlogListResponse(BaseModel):
    items: list[BlogResponse]
    total: int
    limit: int
    skip: int
