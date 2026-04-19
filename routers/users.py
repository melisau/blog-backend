from typing import List

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from core.security import hash_password
from models.blog import Blog
from models.comment import Comment
from models.user import User
from schemas.blog import BlogResponse
from schemas.user import UserPublicResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


async def _blog_to_response(blog: Blog) -> BlogResponse:
    # Populate the category Link before serializing so CategoryResponse fields are available.
    if blog.category:
        await blog.fetch_link(Blog.category)

    # Mirror the engagement-count enrichment from blogs router so the BlogCard
    # in /library and /profile renders identical numbers as the home page.
    comment_count = await Comment.find(Comment.blog_id == blog.id).count()
    favorite_count = await User.find({"favorites": blog.id}).count()

    response = BlogResponse.model_validate(blog)
    response.comment_count = comment_count
    response.favorite_count = favorite_count
    return response


# ── Favorites (/me/favorites) ────────────────────────────────────────────────
# These routes MUST be declared before /{user_id} so that the literal "me"
# segment is not swallowed by the dynamic path parameter.

@router.get("/me/favorites", response_model=List[BlogResponse])
async def list_favorites(
    current_user: User = Depends(get_current_user),
) -> List[BlogResponse]:
    """Return all blogs the authenticated user has saved to their library."""
    if not current_user.favorites:
        return []
    blogs = await Blog.find({"_id": {"$in": current_user.favorites}}).to_list()
    return [await _blog_to_response(b) for b in blogs]


@router.post("/me/favorites/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(
    blog_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Add a blog to the authenticated user's library (idempotent)."""
    try:
        oid = PydanticObjectId(blog_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid blog id.")

    blog = await Blog.get(oid)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    if oid not in current_user.favorites:
        current_user.favorites.append(oid)
        await current_user.save()


@router.delete("/me/favorites/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    blog_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a blog from the authenticated user's library (idempotent)."""
    try:
        oid = PydanticObjectId(blog_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid blog id.")

    if oid in current_user.favorites:
        current_user.favorites.remove(oid)
        await current_user.save()


# ── Following (/me/following) ────────────────────────────────────────────────

@router.get("/me/following", response_model=List[UserPublicResponse])
async def list_following(
    current_user: User = Depends(get_current_user),
) -> List[UserPublicResponse]:
    """Return the list of users the authenticated user is following."""
    if not current_user.following:
        return []
    users = await User.find({"_id": {"$in": current_user.following}}).to_list()
    return [UserPublicResponse.model_validate(u) for u in users]


@router.post("/me/following/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def follow_user(
    target_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Follow another user (idempotent). Cannot follow yourself."""
    try:
        oid = PydanticObjectId(target_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id.")

    if oid == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself.")

    target = await User.get(oid)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if oid not in current_user.following:
        current_user.following.append(oid)
        await current_user.save()


@router.delete("/me/following/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    target_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Unfollow a user (idempotent)."""
    try:
        oid = PydanticObjectId(target_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id.")

    if oid in current_user.following:
        current_user.following.remove(oid)
        await current_user.save()


# ── Public user endpoints (/{ user_id}) ──────────────────────────────────────

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

    if "icon_id" in updated and payload.icon_id is not None:
        user.icon_id = payload.icon_id

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
