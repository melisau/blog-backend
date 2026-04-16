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

    id: PyObjectId
    title: str
    content: str
    author_id: PyObjectId
    category: Optional[CategoryResponse] = None
    tags: List[str]
    cover_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
