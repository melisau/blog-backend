import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import UPLOAD_DIR
from core.database import close_db, init_db
from routers import (
    auth_router,
    blogs_router,
    categories_router,
    comments_router,
    notifications_router,
    users_router,
)

app = FastAPI()

# Statik dosya sunucusu: /uploads/<path> isteklerini UPLOAD_DIR klasöründen karşılar.
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount(f"/{UPLOAD_DIR}", StaticFiles(directory=UPLOAD_DIR), name="uploads")

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(blogs_router)
app.include_router(categories_router)
app.include_router(comments_router)
app.include_router(notifications_router)
app.include_router(users_router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_db()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
