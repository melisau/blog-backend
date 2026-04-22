import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

from core.config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE_MB
from core.deps import get_current_user
from models.blog import Blog
from models.category import Category
from models.comment import Comment
from models.user import User
from schemas.blog import BlogListResponse, BlogResponse
from services.storage import LocalStorageService
from services.storage.base import StorageService

router = APIRouter(prefix="/blogs", tags=["blogs"])

# Application-level singleton; swap LocalStorageService for any StorageService
# implementation (e.g. S3StorageService) without touching the endpoint code.
storage: StorageService = LocalStorageService()


async def _to_response(blog: Blog) -> BlogResponse:
    # Populate the category Link so CategoryResponse fields are available for serialization.
    if blog.category:
        await blog.fetch_link(Blog.category)

    # Engagement counts are computed on read because they live in separate
    # collections (comments) or denormalised arrays (User.favorites). Counting
    # at query time keeps the Blog document free of stale duplicate state.
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
        updated_at=blog.updated_at,
    )
    response.comment_count = comment_count
    response.favorite_count = favorite_count
    return response


async def _validate_and_save_image(
    cover_image: UploadFile,
    storage: StorageService,
) -> str:
    if cover_image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Desteklenmeyen dosya tipi. İzin verilenler: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    contents = await cover_image.read()
    max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dosya boyutu {MAX_IMAGE_SIZE_MB} MB sınırını aşıyor.",
        )

    # Dosya içeriğini tekrar okunabilir hale getir (read() imleci sona taşıdı).
    await cover_image.seek(0)
    return await storage.save_file(cover_image, subfolder="blogs")


def _parse_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='tags geçerli bir JSON dizisi olmalıdır. Örnek: ["python","fastapi"]',
            )
        if not isinstance(parsed, list):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="tags bir dizi olmalıdır.",
            )
        return [str(v) for v in parsed]
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="tags formatı geçersiz.")


async def _resolve_category(category_id: Any) -> Optional[Category]:
    if category_id in (None, ""):
        return None
    try:
        cat_oid = PydanticObjectId(str(category_id))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category id.")
    category = await Category.get(cat_oid)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return category


@router.get("", response_model=BlogListResponse)
async def list_blogs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    category_id: Optional[str] = Query(None, description="Category id to filter by"),
    tag: Optional[str] = Query(None, description="Tag to filter by"),
    q: Optional[str] = Query(None, description="Full-text search on blog title and content"),
    author_id: Optional[str] = Query(None, description="Author id to filter by"),
) -> BlogListResponse:
    mongo_filters: list = []

    if category_id:
        try:
            cat_oid = PydanticObjectId(category_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category id.")
        cat = await Category.get(cat_oid)
        if cat is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        mongo_filters.append({"category.$id": cat.id})

    if tag:
        mongo_filters.append({"tags": tag})
    if q:
        mongo_filters.append({"$text": {"$search": q}})
    if author_id:
        try:
            author_oid = PydanticObjectId(author_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid author id.")
        mongo_filters.append({"author_id": author_oid})

    query = Blog.find(*mongo_filters) if mongo_filters else Blog.find_all()
    total = await query.count()
    blogs = await query.skip(skip).limit(limit).to_list()
    return BlogListResponse(
        items=[await _to_response(b) for b in blogs],
        total=total,
        limit=limit,
        skip=skip,
    )


@router.get("/{blog_id}", response_model=BlogResponse)
async def get_blog(blog_id: str) -> BlogResponse:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")
    return await _to_response(blog)


@router.post("", response_model=BlogResponse, status_code=status.HTTP_201_CREATED)
async def create_blog(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> BlogResponse:
    content_type = request.headers.get("content-type", "")
    cover_image: Optional[UploadFile] = None
    payload: dict[str, Any]
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = dict(form)
        maybe_file = form.get("cover_image")
        if isinstance(maybe_file, UploadFile) and maybe_file.filename:
            cover_image = maybe_file
    else:
        payload = await request.json()

    title = str(payload.get("title", "")).strip()
    content = str(payload.get("content", "")).strip()
    if len(title) < 5 or len(content) < 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Validasyon hatası")

    category = await _resolve_category(payload.get("category_id"))
    parsed_tags = _parse_tags(payload.get("tags"))
    cover_image_url: Optional[str] = None
    if cover_image and cover_image.filename:
        cover_image_url = await _validate_and_save_image(cover_image, storage)

    blog = Blog(
        title=title,
        content=content,
        author_id=current_user.id,
        category=category,
        tags=parsed_tags,
        cover_image_url=cover_image_url,
    )
    await blog.insert()
    return await _to_response(blog)


@router.put("/{blog_id}", response_model=BlogResponse)
async def update_blog(
    blog_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> BlogResponse:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    if blog.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    content_type = request.headers.get("content-type", "")
    cover_image: Optional[UploadFile] = None
    payload: dict[str, Any]
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = dict(form)
        maybe_file = form.get("cover_image")
        if isinstance(maybe_file, UploadFile) and maybe_file.filename:
            cover_image = maybe_file
    else:
        payload = await request.json()

    if "image_url" in payload or "cover_image_url" in payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kapak URL alanlari kabul edilmiyor.")

    title = str(payload.get("title", "")).strip()
    content = str(payload.get("content", "")).strip()
    if len(title) < 5 or len(content) < 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Validasyon hatası")

    remove_cover_image = str(payload.get("remove_cover_image", "false")).lower() == "true"
    if remove_cover_image and cover_image:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="remove_cover_image ve cover_image birlikte kullanılamaz.")

    blog.title = title
    blog.content = content
    blog.tags = _parse_tags(payload.get("tags", []))
    blog.category = await _resolve_category(payload.get("category_id"))  # type: ignore[assignment]

    if remove_cover_image:
        if blog.cover_image_url:
            await storage.delete_file(blog.cover_image_url)
        blog.cover_image_url = None
    elif cover_image and cover_image.filename:
        old_url = blog.cover_image_url
        blog.cover_image_url = await _validate_and_save_image(cover_image, storage)
        if old_url:
            await storage.delete_file(old_url)

    blog.updated_at = datetime.now(timezone.utc)
    await blog.save()
    return await _to_response(blog)


@router.delete("/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog(
    blog_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    if blog.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    if blog.cover_image_url:
        await storage.delete_file(blog.cover_image_url)

    await blog.delete()
