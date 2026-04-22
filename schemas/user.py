from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from schemas.types import PyObjectId


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Full response returned to the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    username: str
    email: EmailStr | None = None
    bio: str | None = None
    icon_id: int | None = None
    created_at: datetime
    updated_at: datetime


class UserPublicResponse(BaseModel):
    """Public profile response that intentionally omits the private email field."""

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    username: str
    bio: str | None = None
    icon_id: int | None = None
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Fields the owner may change on their own profile; all are optional."""

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    bio: Optional[str] = Field(None, max_length=300)
    # Frontend icon library ID; must be a positive integer matching a valid icon.
    icon_id: Optional[int] = Field(None, ge=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserConnectionsResponse(BaseModel):
    """Public follow stats and lists: who this user follows and who follows them (no email)."""

    following: list[UserPublicResponse]
    followers: list[UserPublicResponse]
    following_count: int
    followers_count: int


class UserStatsResponse(BaseModel):
    post_count: int = Field(..., ge=0)
    comment_count: int = Field(..., ge=0)
    followers_count: int = Field(..., ge=0)
    following_count: int = Field(..., ge=0)
