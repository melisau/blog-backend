"""Atomic shared rate counters; TTL removes stale buckets, not active limits."""

import hashlib
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from fastapi import Depends, HTTPException, Request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from core import config
from core.deps import get_current_user
from models.user import User


@dataclass(frozen=True)
class RateLimitPolicy:
    name: str
    limit: int
    seconds: int

    def __post_init__(self) -> None:
        if self.limit < 1 or self.seconds < 1:
            raise ValueError("Rate limits must be positive.")


WRITE_POLICY = RateLimitPolicy("write-ip", config.WRITE_RATE_LIMIT, config.WRITE_RATE_WINDOW_SECONDS)
LOGIN_POLICY = RateLimitPolicy("login-ip", config.LOGIN_RATE_LIMIT, config.LOGIN_RATE_WINDOW_SECONDS)
LOGIN_ACCOUNT_POLICY = RateLimitPolicy("login-account", config.LOGIN_ACCOUNT_RATE_LIMIT, config.LOGIN_ACCOUNT_RATE_WINDOW_SECONDS)
REGISTER_POLICY = RateLimitPolicy("register-ip", config.REGISTER_RATE_LIMIT, config.REGISTER_RATE_WINDOW_SECONDS)
BLOG_POLICY = RateLimitPolicy("blog-user", config.BLOG_RATE_LIMIT, config.BLOG_RATE_WINDOW_SECONDS)
COMMENT_POLICY = RateLimitPolicy("comment-user", config.COMMENT_RATE_LIMIT, config.COMMENT_RATE_WINDOW_SECONDS)


class RateLimitStore(Protocol):
    async def hit(self, key: str, expires_at: datetime) -> int: ...


class MongoRateLimitStore:
    def __init__(self, collection) -> None:
        self.collection = collection

    async def initialize(self) -> None:
        await self.collection.create_index(
            "expires_at", expireAfterSeconds=0, name="rate_limit_expiry",
        )

    async def hit(self, key: str, expires_at: datetime) -> int:
        update = {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": expires_at}}
        try:
            bucket = await self.collection.find_one_and_update(
                {"_id": key}, update, upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            # A concurrent worker created this bucket first. Increment that bucket.
            bucket = await self.collection.find_one_and_update(
                {"_id": key}, update, upsert=False,
                return_document=ReturnDocument.AFTER,
            )
        if bucket is None:
            raise PyMongoError("Rate counter unavailable.")
        return int(bucket["count"])


class RateLimiter:
    def __init__(self, store: RateLimitStore, clock: Callable[[], float] = time.time):
        self.store = store
        self.clock = clock

    async def check(self, policy: RateLimitPolicy, identity: str) -> None:
        now = self.clock()
        window = math.floor(now / policy.seconds)
        window_end = (window + 1) * policy.seconds
        # Never persist raw email addresses, IP addresses or user IDs in buckets.
        key = hashlib.sha256(
            f"{policy.name}:{policy.seconds}:{window}:{identity}".encode(),
        ).hexdigest()
        expires_at = datetime.fromtimestamp(window_end + 60, timezone.utc)
        try:
            count = await self.store.hit(key, expires_at)
        except PyMongoError as exc:
            # Do not silently disable abuse protection when the counter DB fails.
            raise HTTPException(
                status_code=503,
                detail="İstek sınırı doğrulanamıyor. Lütfen tekrar deneyin.",
                headers={"Retry-After": "5"},
            ) from exc
        if count > policy.limit:
            retry_after = max(1, math.ceil(window_end - now))
            raise HTTPException(
                status_code=429,
                detail=f"Çok fazla istek gönderdiniz. {retry_after} saniye sonra tekrar deneyin.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(policy.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )


def client_ip(request: Request) -> str:
    # Forwarded headers are interpreted only by the ASGI server's trusted proxy
    # configuration, never directly from client-supplied X-Forwarded-For here.
    return request.client.host if request.client else "unknown"


async def enforce_limit(request: Request, policy: RateLimitPolicy, identity: str) -> None:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        raise HTTPException(503, "İstek sınırı henüz hazır değil.", headers={"Retry-After": "5"})
    await limiter.check(policy, identity)


async def limit_login(request: Request) -> None:
    await enforce_limit(request, LOGIN_POLICY, client_ip(request))


async def limit_registration(request: Request) -> None:
    await enforce_limit(request, REGISTER_POLICY, client_ip(request))


async def limit_blog_write(request: Request, user: User = Depends(get_current_user)) -> None:
    await enforce_limit(request, BLOG_POLICY, str(user.id))


async def limit_comment_write(request: Request, user: User = Depends(get_current_user)) -> None:
    await enforce_limit(request, COMMENT_POLICY, str(user.id))


class WriteRateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            request = Request(scope)
            try:
                await enforce_limit(request, WRITE_POLICY, client_ip(request))
            except HTTPException as exc:
                response = JSONResponse(
                    {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
