from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from models.comment import Comment
from models.blog import Blog
from models.user import User
from schemas.comment import CommentCreate, CommentResponse

router = APIRouter(tags=["comments"])


@router.get("/blogs/{blog_id}/comments", response_model=List[CommentResponse])
async def list_comments(blog_id: str) -> List[CommentResponse]:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")
    comments = await Comment.find(Comment.blog_id == blog.id).to_list()
    return [CommentResponse.model_validate(c) for c in comments]


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
    return CommentResponse.model_validate(comment)


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
