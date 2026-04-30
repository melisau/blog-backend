from datetime import datetime, timezone

from fastapi import HTTPException, status

from models.blog import Blog
from models.comment import Comment
from models.user import User
from schemas.blog import BlogResponse


def format_created_at_display(created_at: datetime) -> str:
    normalized_created_at = created_at
    if normalized_created_at.tzinfo is None:
        normalized_created_at = normalized_created_at.replace(tzinfo=timezone.utc)
    now = datetime.now(normalized_created_at.tzinfo)

    delta_seconds = max(0, int((now - normalized_created_at).total_seconds()))

    if normalized_created_at.date() == now.date():
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


async def blog_to_response(blog: Blog) -> BlogResponse:
    # Populate category link before serializing category details.
    if blog.category:
        await blog.fetch_link(Blog.category)

    author = await User.get(blog.author_id)
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found.")

    return BlogResponse(
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
        save_count=blog.save_count,
        favorite_count=blog.favorite_count,
        comment_count=blog.comment_count,
        created_at=blog.created_at,
        created_at_display=format_created_at_display(blog.created_at),
        updated_at=blog.updated_at,
    )
