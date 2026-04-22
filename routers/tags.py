from collections import Counter

from fastapi import APIRouter, Query

from models.blog import Blog

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/top")
async def top_tags(limit: int = Query(10, ge=1, le=50)) -> list[dict[str, int | str]]:
    blogs = await Blog.find_all().to_list()
    counter: Counter[str] = Counter()
    for blog in blogs:
        for tag in blog.tags:
            normalized = tag.strip().lower()
            if normalized:
                counter[normalized] += 1

    top = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [{"name": name, "count": count} for name, count in top]
