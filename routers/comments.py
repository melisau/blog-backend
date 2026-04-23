from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from models.comment import Comment
from models.blog import Blog
from models.user import User
from schemas.comment import CommentCreate, CommentResponse

router = APIRouter(tags=["comments"])


def _comment_to_response(
    comment: Comment,
    author_by_id: dict[str, User],
) -> CommentResponse:
    author = author_by_id.get(str(comment.author_id))
    author_payload = None
    if author:
        author_payload = {
            "id": str(author.id),
            "username": author.username,
            "icon_id": author.icon_id,
        }

    return CommentResponse(
        id=str(comment.id),
        blog_id=str(comment.blog_id),
        author_id=str(comment.author_id),
        author=author_payload,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("/blogs/{blog_id}/comments", response_model=List[CommentResponse])
async def list_comments(blog_id: str) -> List[CommentResponse]:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    comments = await Comment.find(Comment.blog_id == blog.id).to_list()
    if not comments:
        return []

    author_ids = list({comment.author_id for comment in comments})
    authors = await User.find({"_id": {"$in": author_ids}}).to_list()
    author_by_id = {str(author.id): author for author in authors}
    return [_comment_to_response(comment, author_by_id) for comment in comments]


@router.post(
    "/blogs/{blog_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    blog_id: str,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    comment = Comment(
        blog_id=blog.id,
        author_id=current_user.id,
        content=payload.content,
    )
    await comment.insert()
    author_by_id = {str(current_user.id): current_user}
    return _comment_to_response(comment, author_by_id)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    comment = await Comment.get(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    # Only the original author may delete their own comment.
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    await comment.delete()
