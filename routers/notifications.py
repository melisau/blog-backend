from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends

from core.deps import get_current_user
from models.blog import Blog
from models.comment import Comment
from models.user import User
from schemas.notification import NotificationItem, NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _build_notifications(current_user: User) -> List[NotificationItem]:
    items: List[NotificationItem] = []

    my_posts = await Blog.find(Blog.author_id == current_user.id).to_list()
    post_ids = [p.id for p in my_posts]

    if post_ids:
        comments = await Comment.find(
            {"blog_id": {"$in": post_ids}, "author_id": {"$ne": current_user.id}}
        ).to_list()
        for c in comments:
            items.append(
                NotificationItem(
                    id=f"comment:{c.id}",
                    type="comment",
                    message="Yazınıza yeni bir yorum yapıldı.",
                    created_at=c.created_at,
                    blog_id=c.blog_id,
                    actor_user_id=c.author_id,
                )
            )

    followers = await User.find({"following": current_user.id, "_id": {"$ne": current_user.id}}).to_list()
    for f in followers:
        items.append(
            NotificationItem(
                id=f"follow:{f.id}",
                type="follow",
                message=f"{f.username} sizi takip etmeye başladı.",
                created_at=f.created_at,
                actor_user_id=f.id,
            )
        )

    items.sort(key=lambda n: n.created_at, reverse=True)
    return items


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    items = await _build_notifications(current_user)
    unread_count = sum(1 for i in items if i.created_at > current_user.notifications_last_read_at)
    return NotificationListResponse(items=items[:30], unread_count=unread_count)


@router.get("/unread-count")
async def unread_count(current_user: User = Depends(get_current_user)):
    items = await _build_notifications(current_user)
    unread = sum(1 for i in items if i.created_at > current_user.notifications_last_read_at)
    return {"unread_count": unread}


@router.post("/mark-read")
async def mark_notifications_read(current_user: User = Depends(get_current_user)):
    current_user.notifications_last_read_at = datetime.now(timezone.utc)
    await current_user.save()
    return {"ok": True}

