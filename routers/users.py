from typing import List

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from core.security import hash_password
from models.blog import Blog
from models.user import User
from schemas.blog import BlogResponse
from schemas.user import UserPublicResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


async def _blog_to_response(blog: Blog) -> BlogResponse:
    # Populate the category Link before serializing so CategoryResponse fields are available.
    if blog.category:
        await blog.fetch_link(Blog.category)
    return BlogResponse.model_validate(blog)


@router.get("/{user_id}", response_model=UserPublicResponse)
async def get_user(user_id: str) -> UserPublicResponse:
    """Return a user's public profile. Email is intentionally excluded."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserPublicResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Update profile information. Only the account owner may call this endpoint."""
    # Prevent one user from modifying another user's profile.
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    updated = payload.model_fields_set

    if "username" in updated and payload.username is not None:
        # Reject the change if another account already holds this username.
        if await User.find_one(User.username == payload.username, User.id != PydanticObjectId(user_id)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken.",
            )
        user.username = payload.username

    if "email" in updated and payload.email is not None:
        # Reject the change if another account already holds this email address.
        if await User.find_one(User.email == payload.email, User.id != PydanticObjectId(user_id)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use.",
            )
        user.email = payload.email

    if "password" in updated and payload.password is not None:
        # Hash the new password before storing; never persist plain text.
        user.hashed_password = hash_password(payload.password)

    await user.save()
    return UserResponse.model_validate(user)


@router.get("/{user_id}/posts", response_model=List[BlogResponse])
async def list_user_posts(user_id: str) -> List[BlogResponse]:
    """Return all blog posts authored by the given user."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Filter blogs by the author's ObjectId stored in the author_id field.
    blogs = await Blog.find(Blog.author_id == user.id).to_list()
    return [await _blog_to_response(b) for b in blogs]
