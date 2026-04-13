from datetime import datetime, timezone
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.deps import get_current_user
from models.category import Category
from models.blog import Blog
from models.user import User
from schemas.blog import BlogCreate, BlogResponse, BlogUpdate

router = APIRouter(prefix="/blogs", tags=["blogs"])


async def _to_response(blog: Blog) -> BlogResponse:
    # Populate the category Link so CategoryResponse fields are available for serialization.
    if blog.category:
        await blog.fetch_link(Blog.category)
    return BlogResponse.model_validate(blog)


@router.get("", response_model=List[BlogResponse])
async def list_blogs(
    # skip: number of records to skip; defaults to 0 (start from the beginning).
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    # limit: maximum number of blogs returned in one request; prevents overloading the client.
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    # category: filter by slug rather than ID so the query string stays human-readable.
    category: Optional[str] = Query(None, description="Category slug to filter by"),
    # search: performs a full-text search against the compound TEXT index (title + content).
    search: Optional[str] = Query(None, description="Full-text search on blog title and content"),
) -> List[BlogResponse]:
    # Conditional filters are collected here; if none are provided all blogs are returned.
    mongo_filters: list = []

    if category:
        # Resolve the slug to a document; return 404 if it does not exist.
        cat = await Category.find_one(Category.slug == category)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        # Beanie stores Link<Category> as a DBRef in MongoDB, so the ObjectId
        # lives at "category.$id", not at "category" directly.
        mongo_filters.append({"category.$id": cat.id})

    if search:
        # Uses the compound TEXT index (title + content) defined in Blog.Settings.indexes.
        # MongoDB's $text operator supports stemming and language-aware matching.
        mongo_filters.append({"$text": {"$search": search}})

    # Blog.find() combines multiple filter dicts with an implicit AND.
    query = Blog.find(*mongo_filters) if mongo_filters else Blog.find_all()
    # .skip() and .limit() map directly to the MongoDB cursor methods of the same name.
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
    payload: BlogCreate,
    current_user: User = Depends(get_current_user),
) -> BlogResponse:
    category: Optional[Category] = None
    if payload.category_id:
        try:
            cat_oid = PydanticObjectId(payload.category_id)
        except Exception:
            # payload.category_id is not a valid 24-hex ObjectId string.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category id."
            )
        category = await Category.get(cat_oid)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found."
            )

    blog = Blog(
        title=payload.title,
        content=payload.content,
        author_id=current_user.id,
        category=category,
        tags=payload.tags,
    )
    await blog.insert()
    return await _to_response(blog)


# PUT semantics: replaces the current resource with the new data.
# Unlike PATCH, PUT signals a full replacement in the HTTP standard;
# BlogUpdate fields are optional, so partial updates are still accepted in practice.
@router.put("/{blog_id}", response_model=BlogResponse)
async def update_blog(
    blog_id: str,
    payload: BlogUpdate,
    current_user: User = Depends(get_current_user),
) -> BlogResponse:
    blog = await Blog.get(blog_id)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found.")

    # Only the original author may edit the blog.
    if blog.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    updated = payload.model_fields_set
    if "title" in updated and payload.title is not None:
        blog.title = payload.title
    if "content" in updated and payload.content is not None:
        blog.content = payload.content
    if "tags" in updated and payload.tags is not None:
        blog.tags = payload.tags
    if "category_id" in updated:
        if payload.category_id is None:
            blog.category = None
        else:
            try:
                cat_oid = PydanticObjectId(payload.category_id)
            except Exception:
                # payload.category_id is not a valid 24-hex ObjectId string.
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category id."
                )
            category = await Category.get(cat_oid)
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Category not found."
                )
            # Assign the full Category document so Beanie can call .to_ref() during save.
            blog.category = category  # type: ignore[assignment]

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

    await blog.delete()
