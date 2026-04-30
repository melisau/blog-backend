from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends

from core.deps import get_current_user
from models.blog import Blog
from models.comment import Comment
from models.follow_event import FollowEvent
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

        commenter_ids = list({c.author_id for c in comments})
        username_by_id: dict = {}
        if commenter_ids:
            commenters = await User.find({"_id": {"$in": commenter_ids}}).to_list()
            username_by_id = {u.id: u.username for u in commenters}

        for c in comments:
            is_read = c.created_at <= current_user.notifications_last_read_at
            commenter_name = username_by_id.get(c.author_id, "Bir kullanıcı")
            items.append(
                NotificationItem(
                    id=f"comment:{c.id}",
                    type="comment",
                    message=f"{commenter_name} yazınıza yeni bir yorum yaptı.",
                    created_at=c.created_at,
                    read=is_read,
                    blog_id=c.blog_id,
                    actor_user_id=c.author_id,
                )
            )

    followers = await User.find({"following": current_user.id, "_id": {"$ne": current_user.id}}).to_list()
    follower_ids = [f.id for f in followers]
    follow_events = (
        await FollowEvent.find(
            {"following_id": current_user.id, "follower_id": {"$in": follower_ids}}
        ).to_list()
        if follower_ids
        else []
    )
    follow_created_at_by_follower_id = {event.follower_id: event.created_at for event in follow_events}

    for f in followers:
        follow_created_at = follow_created_at_by_follower_id.get(f.id, f.created_at)
        is_read = follow_created_at <= current_user.notifications_last_read_at
        items.append(
            NotificationItem(
                id=f"follow:{f.id}",
                type="follow",
                message=f"{f.username} sizi takip etmeye başladı.",
                created_at=follow_created_at,
                read=is_read,
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

