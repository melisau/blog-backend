from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.category import CategoryResponse


class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category_id: Optional[str] = None
    tags: Optional[List[str]] = None


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    content: str
    author_id: str
    category: Optional[CategoryResponse] = None
    tags: List[str]
    created_at: datetime
    updated_at: datetime
