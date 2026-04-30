import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

from core.config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE_MB
from core.deps import get_current_user
from models.blog import Blog
from models.category import Category
from models.user import User
from schemas.blog import BlogListResponse, BlogResponse
from services.blog_presenter import blog_to_response
from services.storage import LocalStorageService
from services.storage.base import StorageService

router = APIRouter(prefix="/blogs", tags=["blogs"])

# Application-level singleton; swap LocalStorageService for any StorageService
# implementation (e.g. S3StorageService) without touching the endpoint code.
storage: StorageService = LocalStorageService()


async def _validate_and_save_image(
    cover_image: UploadFile,
    storage: StorageService,
) -> str:
    print(f"DEBUG: Uploading file {cover_image.filename} with type {cover_image.content_type}")
    if cover_image.content_type not in ALLOWED_IMAGE_TYPES:
        print(f"DEBUG: Unsupported media type: {cover_image.content_type}")
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Desteklenmeyen dosya tipi ({cover_image.content_type}). İzin verilenler: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    contents = await cover_image.read()
    file_size = len(contents)
    print(f"DEBUG: File size: {file_size} bytes")
    max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        print(f"DEBUG: File too large: {file_size} > {max_bytes}")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dosya boyutu {MAX_IMAGE_SIZE_MB} MB sınırını aşıyor.",
        )

    # Dosya içeriğini tekrar okunabilir hale getir (read() imleci sona taşıdı).
    await cover_image.seek(0)
    url = await storage.save_file(cover_image, subfolder="blogs")
    print(f"DEBUG: File saved at {url}")
    return url


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


def _normalize_tag_query(raw_tag: Optional[str], raw_tags: Optional[str]) -> Optional[str]:
    value = raw_tag if raw_tag not in (None, "") else raw_tags
    if value is None:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    if normalized.startswith("{") and normalized.endswith("}"):
        try:
            parsed = json.loads(normalized)
        except (json.JSONDecodeError, ValueError):
            return normalized
        if isinstance(parsed, dict):
            for key in ("name", "tag", "value", "label"):
                candidate = parsed.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
    return normalized


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
    category: Optional[str] = Query(None, description="Legacy category slug/name filter"),
    tag: Optional[str] = Query(None, description="Tag to filter by"),
    tags: Optional[str] = Query(None, description="Legacy tag query alias"),
    q: Optional[str] = Query(None, description="Full-text search on blog title and content"),
    search: Optional[str] = Query(None, description="Legacy full-text search alias"),
    author_id: Optional[str] = Query(None, description="Author id to filter by"),
    sort: str = Query("newest", description="Sorting criteria: 'newest' or 'popular'"),
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
    elif category:
        # Backward compatible filter: support both slug and human-readable name.
        cat = await Category.find_one(
            {
                "$or": [
                    {"slug": {"$regex": f"^{category}$", "$options": "i"}},
                    {"name": {"$regex": f"^{category}$", "$options": "i"}},
                ]
            }
        )
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        mongo_filters.append({"category.$id": cat.id})

    normalized_tag = _normalize_tag_query(tag, tags)
    if normalized_tag:
        tag_pattern = f"^{re.escape(normalized_tag)}$"
        mongo_filters.append(
            {
                "$or": [
                    {"tags": {"$regex": tag_pattern, "$options": "i"}},
                    {"tags.name": {"$regex": tag_pattern, "$options": "i"}},
                ]
            }
        )
    query_text = (q or search or "").strip()
    if query_text:
        escaped = re.escape(query_text)
        mongo_filters.append(
            {
                "$or": [
                    {"title": {"$regex": escaped, "$options": "i"}},
                    {"content": {"$regex": escaped, "$options": "i"}},
                    {"tags": {"$regex": escaped, "$options": "i"}},
                    {"tags.name": {"$regex": escaped, "$options": "i"}},
                ]
            }
        )
    if author_id:
        try:
            author_oid = PydanticObjectId(author_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid author id.")
        mongo_filters.append({"author_id": author_oid})

    if sort == "popular":
        # To sort by a sum of fields, we use an aggregation pipeline to compute
        # a temporary 'interaction_score' field.
        pipeline: list[dict[str, Any]] = []
        if mongo_filters:
            # Beanie's find(*filters) implicitly ANDs them.
            pipeline.append({"$match": {"$and": mongo_filters} if len(mongo_filters) > 1 else mongo_filters[0]})
        
        pipeline.extend([
            {
                "$addFields": {
                    "interaction_score": {
                        "$add": ["$favorite_count", "$save_count", "$comment_count"]
                    }
                }
            },
            {"$sort": {"interaction_score": -1, "created_at": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ])
        
        # For total count, we still use the standard find query.
        count_query = Blog.find(*mongo_filters) if mongo_filters else Blog.find_all()
        total = await count_query.count()
        
        # Beanie's aggregate returns raw dictionaries.
        raw_blogs = await Blog.aggregate(pipeline).to_list()
        blogs = [Blog.model_validate(b) for b in raw_blogs]
    else:
        # Default: newest (created_at descending)
        query = Blog.find(*mongo_filters) if mongo_filters else Blog.find_all()
        query = query.sort([("created_at", -1)])
        total = await query.count()
        blogs = await query.skip(skip).limit(limit).to_list()

    return BlogListResponse(
        items=[await blog_to_response(b) for b in blogs],
        total=total,
        limit=limit,
        skip=skip,
    )


@router.get("/{blog_id}", response_model=BlogResponse)
async def get_blog(blog_id: str) -> BlogResponse:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")
    return await blog_to_response(blog)


@router.post("", response_model=BlogResponse, status_code=status.HTTP_201_CREATED)
async def create_blog(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> BlogResponse:
    content_type = request.headers.get("content-type", "")
    print(f"DEBUG: Received request with content-type: {content_type}")
    cover_image: Optional[UploadFile] = None
    payload: dict[str, Any]
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = dict(form)
        maybe_file = form.get("cover_image")
        if maybe_file and getattr(maybe_file, "filename", None):
            cover_image = maybe_file
            print(f"DEBUG: Found cover_image: {cover_image.filename}")
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
    return await blog_to_response(blog)


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
        if maybe_file and getattr(maybe_file, "filename", None):
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
    return await blog_to_response(blog)


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
