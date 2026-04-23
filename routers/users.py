from datetime import datetime, timezone
from typing import List

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.deps import get_current_user
from models.blog import Blog
from models.comment import Comment
from models.user import User
from schemas.blog import BlogResponse
from schemas.user import (
    UserConnectionsResponse,
    UserPublicResponse,
    UserResponse,
    UserStatsResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


def _format_created_at_display(created_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    normalized_created_at = created_at
    if normalized_created_at.tzinfo is None:
        normalized_created_at = normalized_created_at.replace(tzinfo=timezone.utc)

    delta_seconds = max(0, int((now - normalized_created_at).total_seconds()))
    one_day_seconds = 24 * 60 * 60

    if delta_seconds < one_day_seconds:
        hours = delta_seconds // 3600
        if hours == 0:
            minutes = max(1, delta_seconds // 60)
            if minutes < 60:
                if minutes == 30:
                    return "yarım saat önce eklendi"
                return f"{minutes} dakika önce eklendi"
            return "1 saat önce eklendi"
        return f"{hours} saat önce eklendi"

    return normalized_created_at.strftime("%d.%m.%Y %H:%M")


async def _blog_to_response(blog: Blog) -> BlogResponse:
    # Populate the category Link before serializing so CategoryResponse fields are available.
    if blog.category:
        await blog.fetch_link(Blog.category)

    # Mirror the engagement-count enrichment from blogs router so the BlogCard
    # in /library and /profile renders identical numbers as the home page.
    comment_count = await Comment.find(Comment.blog_id == blog.id).count()
    favorite_count = await User.find({"favorites": blog.id}).count()

    author = await User.get(blog.author_id)
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found.")

    response = BlogResponse(
        id=str(blog.id),
        title=blog.title,
        content=blog.content,
        author={
            "id": str(author.id),
            "username": author.username,
            "icon_id": author.icon_id,
        },
        category=blog.category,
        tags=blog.tags,
        cover_image_url=blog.cover_image_url,
        created_at=blog.created_at,
        created_at_display=_format_created_at_display(blog.created_at),
        updated_at=blog.updated_at,
    )
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

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return authenticated user's own profile including email."""
    return UserResponse.model_validate(current_user)


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


# ── Public follow lists (/users/{id}/following, /users/{id}/followers) ───────

@router.get("/{user_id}/following", response_model=List[UserPublicResponse])
async def list_user_following(
    user_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
) -> List[UserPublicResponse]:
    """Return users that the given user follows (paginated)."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if not user.following:
        return []
    users = await User.find({"_id": {"$in": user.following}}).skip(skip).limit(limit).to_list()
    return [UserPublicResponse.model_validate(u) for u in users]


@router.get("/{user_id}/followers", response_model=List[UserPublicResponse])
async def list_user_followers(
    user_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
) -> List[UserPublicResponse]:
    """Return users that follow the given user (paginated)."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    followers = await User.find({"following": user.id}).skip(skip).limit(limit).to_list()
    return [UserPublicResponse.model_validate(u) for u in followers]


@router.get("/{user_id}/connections", response_model=UserConnectionsResponse)
async def get_user_connections(user_id: str) -> UserConnectionsResponse:
    """Following/follower lists and counts in one public payload (no email)."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    following_users = (
        await User.find({"_id": {"$in": user.following}}).to_list()
        if user.following
        else []
    )
    follower_users = await User.find({"following": user.id}).to_list()

    following = [UserPublicResponse.model_validate(u) for u in following_users]
    followers = [UserPublicResponse.model_validate(u) for u in follower_users]

    return UserConnectionsResponse(
        following=following,
        followers=followers,
        following_count=len(following),
        followers_count=len(followers),
    )


# ── Public user endpoints (/{ user_id}) ──────────────────────────────────────

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str) -> UserResponse:
    """Return a user's public profile. Email is never returned here."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    response = UserResponse.model_validate(user)
    response.email = None
    return response


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Update profile information. Only the account owner may call this endpoint."""
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu profili düzenleyemezsiniz.")

    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    updated = payload.model_fields_set

    if "username" in updated and payload.username is not None:
        if await User.find_one(User.username == payload.username, User.id != PydanticObjectId(user_id)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu kullanıcı adı zaten kullanılıyor.",
            )
        user.username = payload.username

    if "bio" in updated:
        user.bio = payload.bio

    if "icon_id" in updated:
        user.icon_id = payload.icon_id

    user.updated_at = datetime.now(timezone.utc)
    await user.save()
    return UserResponse.model_validate(user)


@router.get("/{user_id}/stats", response_model=UserStatsResponse)
async def get_user_stats(user_id: str) -> UserStatsResponse:
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    post_count = await Blog.find(Blog.author_id == user.id).count()
    comment_count = await Comment.find(Comment.author_id == user.id).count()
    followers_count = await User.find({"following": user.id}).count()
    following_count = len(user.following)
    return UserStatsResponse(
        post_count=post_count,
        comment_count=comment_count,
        followers_count=followers_count,
        following_count=following_count,
    )


@router.get("/{user_id}/posts", response_model=List[BlogResponse])
async def list_user_posts(user_id: str) -> List[BlogResponse]:
    """Return all blog posts authored by the given user."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Filter blogs by the author's ObjectId stored in the author_id field.
    blogs = await Blog.find(Blog.author_id == user.id).to_list()
    return [await _blog_to_response(b) for b in blogs]
