import json
from datetime import datetime, timezone
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from core.config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE_MB
from core.deps import get_current_user
from models.blog import Blog
from models.category import Category
from models.user import User
from schemas.blog import BlogResponse
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
    return BlogResponse.model_validate(blog)


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


@router.get("", response_model=List[BlogResponse])
async def list_blogs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    category: Optional[str] = Query(None, description="Category slug to filter by"),
    search: Optional[str] = Query(None, description="Full-text search on blog title and content"),
) -> List[BlogResponse]:
    mongo_filters: list = []

    if category:
        cat = await Category.find_one(Category.slug == category)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        mongo_filters.append({"category.$id": cat.id})

    if search:
        mongo_filters.append({"$text": {"$search": search}})

    query = Blog.find(*mongo_filters) if mongo_filters else Blog.find_all()
    blogs = await query.skip(skip).limit(limit).to_list()
    return [await _to_response(b) for b in blogs]


@router.get("/{blog_id}", response_model=BlogResponse)
async def get_blog(blog_id: str) -> BlogResponse:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")
    return await _to_response(blog)


@router.post("", response_model=BlogResponse, status_code=status.HTTP_201_CREATED)
async def create_blog(
    title: str = Form(..., min_length=1, max_length=200),
    content: str = Form(..., min_length=1),
    category_id: Optional[str] = Form(None),
    # Frontend'den JSON dizisi olarak gönderilmeli: '["python","fastapi"]'
    tags: str = Form("[]"),
    cover_image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
) -> BlogResponse:
    try:
        parsed_tags: List[str] = json.loads(tags)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tags geçerli bir JSON dizisi olmalıdır. Örnek: '[\"python\",\"fastapi\"]'",
        )

    category: Optional[Category] = None
    if category_id:
        try:
            cat_oid = PydanticObjectId(category_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category id."
            )
        category = await Category.get(cat_oid)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found."
            )

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
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    # None → değişiklik yok; boş dosya adı → kapak fotoğrafı kaldır; yeni dosya → güncelle
    cover_image: Optional[UploadFile] = File(None),
    remove_cover_image: bool = Form(False),
    current_user: User = Depends(get_current_user),
) -> BlogResponse:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    if blog.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    if title is not None:
        blog.title = title
    if content is not None:
        blog.content = content

    if tags is not None:
        try:
            blog.tags = json.loads(tags)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="tags geçerli bir JSON dizisi olmalıdır. Örnek: '[\"python\",\"fastapi\"]'",
            )

    # category_id form alanı gönderildiyse işle (boş string → kategoriyi kaldır)
    if category_id is not None:
        if category_id == "":
            blog.category = None
        else:
            try:
                cat_oid = PydanticObjectId(category_id)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category id."
                )
            category = await Category.get(cat_oid)
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Category not found."
                )
            blog.category = category  # type: ignore[assignment]

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
