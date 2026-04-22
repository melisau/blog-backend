from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from models.category import Category
from models.user import User
from schemas.category import CategoryCreate, CategoryListResponse, CategoryResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
async def list_categories() -> CategoryListResponse:
    categories = await Category.find_all().to_list()
    return CategoryListResponse(items=[CategoryResponse.model_validate(c) for c in categories])


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: str) -> CategoryResponse:
    category = await Category.get(category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return CategoryResponse.model_validate(category)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    _: User = Depends(get_current_user),
) -> CategoryResponse:
    if await Category.find_one(Category.slug == payload.slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A category with this slug already exists.",
        )
    category = Category(name=payload.name, slug=payload.slug)
    await category.insert()
    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    _: User = Depends(get_current_user),
) -> None:
    category = await Category.get(category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    await category.delete()
