from datetime import datetime, timezone
from typing import List

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.deps import get_current_user
from models.blog import Blog
from models.comment import Comment
from models.favorite import Favorite
from models.follow_event import FollowEvent
from models.saved_blog import SavedBlog
from models.user import User
from schemas.blog import BlogResponse
from schemas.user import (
    UserConnectionsResponse,
    UserPublicResponse,
    UserResponse,
    UserStatsResponse,
    UserUpdate,
)
from services.blog_presenter import blog_to_response

router = APIRouter(prefix="/users", tags=["users"])


# ── Library (/me/library) ──────────────────────────────────────────────────
# These routes MUST be declared before /{user_id} so that the literal "me"
# segment is not swallowed by the dynamic path parameter.

@router.get("/me/library", response_model=List[BlogResponse])
async def list_library(
    current_user: User = Depends(get_current_user),
) -> List[BlogResponse]:
    """Return all blogs the authenticated user has saved to their library."""
    saved = await SavedBlog.find(SavedBlog.user_id == current_user.id).to_list()
    if not saved:
        return []
    blog_ids = [s.blog_id for s in saved]
    blogs = await Blog.find({"_id": {"$in": blog_ids}}).to_list()
    return [await blog_to_response(b) for b in blogs]


@router.post("/me/library/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_to_library(
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

    saved = await SavedBlog.find_one(
        SavedBlog.user_id == current_user.id,
        SavedBlog.blog_id == oid,
    )
    if not saved:
        await SavedBlog(user_id=current_user.id, blog_id=oid).insert()
        await blog.update({"$inc": {"save_count": 1}})


@router.delete("/me/library/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_library(
    blog_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a blog from the authenticated user's library (idempotent)."""
    try:
        oid = PydanticObjectId(blog_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid blog id.")

    saved = await SavedBlog.find_one(
        SavedBlog.user_id == current_user.id,
        SavedBlog.blog_id == oid,
    )
    if saved:
        await saved.delete()
        await Blog.find_one(Blog.id == oid).update({"$inc": {"save_count": -1}})


# ── Likes (/me/likes) ─────────────────────────────────────────────────────

@router.get("/me/likes", response_model=List[BlogResponse])
async def list_likes(
    current_user: User = Depends(get_current_user),
) -> List[BlogResponse]:
    """Return all blogs the authenticated user has liked."""
    favorites = await Favorite.find(Favorite.user_id == current_user.id).to_list()
    if not favorites:
        return []
    blog_ids = [f.blog_id for f in favorites]
    blogs = await Blog.find({"_id": {"$in": blog_ids}}).to_list()
    return [await blog_to_response(b) for b in blogs]


@router.post("/me/likes/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_like(
    blog_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Toggle like for a blog."""
    try:
        oid = PydanticObjectId(blog_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid blog id.")

    blog = await Blog.get(oid)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    favorite = await Favorite.find_one(
        Favorite.user_id == current_user.id,
        Favorite.blog_id == oid,
    )
    if favorite:
        await favorite.delete()
        await blog.update({"$inc": {"favorite_count": -1}})
    else:
        await Favorite(user_id=current_user.id, blog_id=oid).insert()
        await blog.update({"$inc": {"favorite_count": 1}})


@router.delete("/me/likes/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_like(
    blog_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove like from a blog (idempotent)."""
    try:
        oid = PydanticObjectId(blog_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid blog id.")

    favorite = await Favorite.find_one(
        Favorite.user_id == current_user.id,
        Favorite.blog_id == oid,
    )
    if favorite:
        await favorite.delete()
        await Blog.find_one(Blog.id == oid).update({"$inc": {"favorite_count": -1}})


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
    events = await FollowEvent.find(FollowEvent.follower_id == current_user.id).to_list()
    if not events:
        return []
    ids = [e.following_id for e in events]
    users = await User.find({"_id": {"$in": ids}}).to_list()
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

    follow_event = await FollowEvent.find_one(
        FollowEvent.follower_id == current_user.id,
        FollowEvent.following_id == oid,
    )
    if not follow_event:
        await FollowEvent(
            follower_id=current_user.id,
            following_id=oid,
            created_at=datetime.now(timezone.utc),
        ).insert()
        # Atomic increments
        await current_user.update({"$inc": {"following_count": 1}})
        await target.update({"$inc": {"followers_count": 1}})


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

    follow_event = await FollowEvent.find_one(
        FollowEvent.follower_id == current_user.id,
        FollowEvent.following_id == oid,
    )
    if follow_event:
        await follow_event.delete()
        # Atomic decrements
        await current_user.update({"$inc": {"following_count": -1}})
        await User.find_one(User.id == oid).update({"$inc": {"followers_count": -1}})


# ── Public follow lists (/users/{id}/following, /users/{id}/followers) ───────

@router.get("/{user_id}/following", response_model=List[UserPublicResponse])
async def list_user_following(
    user_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
) -> List[UserPublicResponse]:
    """Return users that the given user follows (paginated)."""
    try:
        oid = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id.")

    events = await FollowEvent.find(FollowEvent.follower_id == oid).skip(skip).limit(limit).to_list()
    if not events:
        return []
    ids = [e.following_id for e in events]
    users = await User.find({"_id": {"$in": ids}}).to_list()
    return [UserPublicResponse.model_validate(u) for u in users]


@router.get("/{user_id}/followers", response_model=List[UserPublicResponse])
async def list_user_followers(
    user_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
) -> List[UserPublicResponse]:
    """Return users that follow the given user (paginated)."""
    try:
        oid = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id.")

    events = await FollowEvent.find(FollowEvent.following_id == oid).skip(skip).limit(limit).to_list()
    if not events:
        return []
    ids = [e.follower_id for e in events]
    users = await User.find({"_id": {"$in": ids}}).to_list()
    return [UserPublicResponse.model_validate(u) for u in users]


@router.get("/{user_id}/connections", response_model=UserConnectionsResponse)
async def get_user_connections(user_id: str) -> UserConnectionsResponse:
    """Following/follower lists and counts in one public payload (no email)."""
    try:
        oid = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id.")

    user = await User.get(oid)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    following_events = await FollowEvent.find(FollowEvent.follower_id == oid).to_list()
    follower_events = await FollowEvent.find(FollowEvent.following_id == oid).to_list()

    following_ids = [e.following_id for e in following_events]
    follower_ids = [e.follower_id for e in follower_events]

    following_users = await User.find({"_id": {"$in": following_ids}}).to_list()
    follower_users = await User.find({"_id": {"$in": follower_ids}}).to_list()

    following = [UserPublicResponse.model_validate(u) for u in following_users]
    followers = [UserPublicResponse.model_validate(u) for u in follower_users]

    return UserConnectionsResponse(
        following=following,
        followers=followers,
        following_count=user.following_count,
        followers_count=user.followers_count,
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
    try:
        oid = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id.")

    user = await User.get(oid)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    post_count = await Blog.find(Blog.author_id == user.id).count()
    comment_count = await Comment.find(Comment.author_id == user.id).count()
    return UserStatsResponse(
        post_count=post_count,
        comment_count=comment_count,
        followers_count=user.followers_count,
        following_count=user.following_count,
    )


@router.get("/{user_id}/posts", response_model=List[BlogResponse])
async def list_user_posts(user_id: str) -> List[BlogResponse]:
    """Return all blog posts authored by the given user."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Filter blogs by the author's ObjectId stored in the author_id field.
    blogs = await Blog.find(Blog.author_id == user.id).to_list()
    return [await blog_to_response(b) for b in blogs]
