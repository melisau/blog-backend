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
    """Full response returned to the authenticated user (includes email)."""

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    username: str
    email: EmailStr
    created_at: datetime


class UserPublicResponse(BaseModel):
    """Public profile response that intentionally omits the private email field."""

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    username: str
    created_at: datetime


class UserUpdate(BaseModel):
    """Fields the owner may change on their own profile; all are optional."""

    username: Optional[str] = Field(None, min_length=1, max_length=64)
    # Changing the email requires re-uniqueness validation in the router.
    email: Optional[EmailStr] = None
    # Plain-text password; the router is responsible for hashing before persisting.
    password: Optional[str] = Field(None, min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
