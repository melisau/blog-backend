import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import CORS_ORIGINS, MONGODB_DB_NAME, UPLOAD_DIR
from core.database import close_db, init_db
from core.rate_limit import MongoRateLimitStore, RateLimiter, WriteRateLimitMiddleware
from routers import (
    auth_router,
    blogs_router,
    categories_router,
    comments_router,
    notifications_router,
    tags_router,
    users_router,
)

app = FastAPI()

# Statik dosya sunucusu: /uploads/<path> isteklerini UPLOAD_DIR klasöründen karşılar.
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount(f"/{UPLOAD_DIR}", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(WriteRateLimitMiddleware)

# CORS stays outside the limiter so 429/503 responses also reach the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)


app.include_router(auth_router)
app.include_router(blogs_router)
app.include_router(categories_router)
app.include_router(comments_router)
app.include_router(notifications_router)
app.include_router(tags_router)
app.include_router(users_router)


@app.on_event("startup")
async def on_startup() -> None:
    client = await init_db()
    store = MongoRateLimitStore(client[MONGODB_DB_NAME]["rate_limit_buckets"])
    await store.initialize()
    app.state.rate_limiter = RateLimiter(store)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_db()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
