from pydantic import BaseModel, ConfigDict, Field

from schemas.types import PyObjectId


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    name: str
    slug: str


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
