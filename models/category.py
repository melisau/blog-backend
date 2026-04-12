from beanie import Document
from pydantic import Field


class Category(Document):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)

    class Settings:
        name = "categories"
