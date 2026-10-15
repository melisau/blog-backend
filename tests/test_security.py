import asyncio
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from pydantic import ValidationError
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from core import security
from core.deps import get_current_user
from core.rate_limit import MongoRateLimitStore, RateLimitPolicy, RateLimiter, WriteRateLimitMiddleware
from core.roles import UserRole
from models.category import Category
from models.user import User
from routers.auth import router as auth_router
from routers.blogs import router as blogs_router
from routers.categories import router as categories_router
from routers.comments import router as comments_router
from schemas.user import UserCreate, UserUpdate
from scripts.set_user_role import change_role
from scripts.provision_admin import provision

USER_ID = "507f1f77bcf86cd799439011"
CATEGORY_ID = "507f1f77bcf86cd799439012"


class AtomicTestStore:
    """Test double only; production always uses MongoDB."""

    def __init__(self):
        self.buckets = {}
        self.lock = asyncio.Lock()

    async def hit(self, key, expires_at):
        async with self.lock:
            self.buckets[key] = self.buckets.get(key, 0) + 1
            return self.buckets[key]


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.secret = patch.object(security, "JWT_SECRET", "test-only-secret-not-a-real-credential")
        self.algorithm = patch.object(security, "JWT_ALGORITHM", "HS256")
        self.ttl = patch.object(security, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)
        for patcher in (self.secret, self.algorithm, self.ttl):
            patcher.start()
            self.addCleanup(patcher.stop)

    def encode(self, claims):
        return jwt.encode(claims, security.JWT_SECRET, algorithm="HS256")

    def test_new_token_has_thirty_minutes_not_days(self):
        token = security.create_access_token(USER_ID)
        claims = jwt.get_unverified_claims(token)
        self.assertEqual(claims["exp"] - claims["iat"], 30 * 60)
        self.assertEqual(security.decode_access_token(token), USER_ID)

    def test_old_long_lived_tokens_and_missing_expiry_are_rejected(self):
        now = int(time.time())
        for claims in (
            {"sub": USER_ID, "exp": now + 30 * 86400},
            {"sub": USER_ID, "iat": now, "exp": now + 30 * 86400},
            {"sub": USER_ID, "iat": now},
        ):
            with self.subTest(claims=claims), self.assertRaises(JWTError):
                security.decode_access_token(self.encode(claims))

    def test_expired_future_and_tampered_tokens_are_rejected(self):
        now = int(time.time())
        for claims in (
            {"sub": USER_ID, "iat": now - 1900, "exp": now - 100},
            {"sub": USER_ID, "iat": now + 600, "exp": now + 2400},
        ):
            with self.subTest(claims=claims), self.assertRaises(JWTError):
                security.decode_access_token(self.encode(claims))
        forged = jwt.encode(
            {"sub": USER_ID, "iat": now, "exp": now + 1800},
            "a-different-test-only-secret", algorithm="HS256",
        )
        with self.assertRaises(JWTError):
            security.decode_access_token(forged)

    def test_authenticated_route_rejects_expired_token(self):
        now = int(time.time())
        token = self.encode({"sub": USER_ID, "iat": now - 1900, "exp": now - 100})
        app = FastAPI()
        app.include_router(auth_router)
        response = TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_malformed_subject_is_unauthorized_not_a_server_error(self):
        now = int(time.time())
        token = self.encode({"sub": "invalid-object-id", "iat": now, "exp": now + 1800})
        app = FastAPI()
        app.include_router(auth_router)
        response = TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)


class CategoryAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(categories_router)
        self.client = TestClient(self.app)
        self.category = SimpleNamespace(
            id=PydanticObjectId(CATEGORY_ID), name="Test", slug="test", delete=AsyncMock(),
        )

    def as_role(self, role):
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID, role=role)

    def test_guest_cannot_create_or_delete_category(self):
        self.assertEqual(self.client.post("/categories", json={"name": "Test", "slug": "test"}).status_code, 401)
        self.assertEqual(self.client.delete(f"/categories/{CATEGORY_ID}").status_code, 401)

    def test_user_cannot_create_or_delete_category(self):
        self.as_role(UserRole.USER)
        with patch.object(Category, "find_one", new_callable=AsyncMock) as find:
            self.assertEqual(self.client.post("/categories", json={"name": "Test", "slug": "test"}).status_code, 403)
            self.assertEqual(self.client.delete(f"/categories/{CATEGORY_ID}").status_code, 403)
            find.assert_not_awaited()

    def test_admin_can_create_category(self):
        self.as_role(UserRole.ADMIN)
        # Patch field expressions and the document constructor without a live DB.
        with patch("routers.categories.Category") as model:
            model.slug = "slug"
            model.find_one = AsyncMock(return_value=None)
            model.return_value = self.category
            self.category.insert = AsyncMock()
            response = self.client.post("/categories", json={"name": "Test", "slug": "test"})
        self.assertEqual(response.status_code, 201, response.text)
        self.category.insert.assert_awaited_once()

    def test_admin_can_delete_unused_category_but_not_used_category(self):
        self.as_role(UserRole.ADMIN)
        with patch.object(Category, "get", new_callable=AsyncMock, return_value=self.category), patch("routers.categories.Blog") as blogs:
            blogs.find.return_value.count = AsyncMock(return_value=1)
            self.assertEqual(self.client.delete(f"/categories/{CATEGORY_ID}").status_code, 409)
            self.category.delete.assert_not_awaited()
            blogs.find.return_value.count.return_value = 0
            self.assertEqual(self.client.delete(f"/categories/{CATEGORY_ID}").status_code, 204)
            self.category.delete.assert_awaited_once()

    def test_public_category_list_stays_public(self):
        with patch.object(Category, "find_all") as find:
            find.return_value.to_list = AsyncMock(return_value=[])
            self.assertEqual(self.client.get("/categories").status_code, 200)

    def test_legacy_role_defaults_to_user_and_payload_cannot_promote(self):
        self.assertEqual(User.model_fields["role"].default, UserRole.USER)
        with self.assertRaises(ValidationError):
            UserCreate(username="test", email="test@example.com", password="password123", role="admin")
        with self.assertRaises(ValidationError):
            UserUpdate(role="admin")

    def test_role_claim_in_token_does_not_override_database_role(self):
        now = int(time.time())
        claims = {"sub": USER_ID, "iat": now, "exp": now + security.ACCESS_TOKEN_EXPIRE_MINUTES * 60, "role": "admin"}
        with patch.object(security, "JWT_SECRET", "test-only-role-claim-secret"):
            token = jwt.encode(claims, security.JWT_SECRET, algorithm=security.JWT_ALGORITHM)
            with patch.object(User, "get", new_callable=AsyncMock, return_value=SimpleNamespace(id=USER_ID, role=UserRole.USER)):
                response = self.client.post("/categories", json={"name": "Test", "slug": "test"}, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)


class LimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_window_reset_independent_users_and_retry_after(self):
        now = [120.25]
        store = AtomicTestStore()
        limiter = RateLimiter(store, clock=lambda: now[0])
        policy = RateLimitPolicy("test", 2, 60)
        await limiter.check(policy, "first")
        await limiter.check(policy, "first")
        with self.assertRaises(HTTPException) as caught:
            await limiter.check(policy, "first")
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.headers["Retry-After"], "60")
        await limiter.check(policy, "second")
        now[0] = 180
        await limiter.check(policy, "first")

    async def test_parallel_requests_across_workers_share_the_same_budget(self):
        store = AtomicTestStore()
        workers = [RateLimiter(store, clock=lambda: 120) for _ in range(3)]
        policy = RateLimitPolicy("shared", 5, 60)
        results = await asyncio.gather(
            *(workers[i % 3].check(policy, "same-user") for i in range(30)),
            return_exceptions=True,
        )
        self.assertEqual(sum(result is None for result in results), 5)
        self.assertEqual(sum(isinstance(result, HTTPException) and result.status_code == 429 for result in results), 25)

    async def test_database_failure_does_not_disable_limits(self):
        store = SimpleNamespace(hit=AsyncMock(side_effect=ConnectionFailure("test")))
        with self.assertRaises(HTTPException) as caught:
            await RateLimiter(store).check(RateLimitPolicy("test", 1, 60), "user")
        self.assertEqual(caught.exception.status_code, 503)

    async def test_mongo_counter_is_atomic_hashed_and_has_ttl(self):
        collection = SimpleNamespace(
            create_index=AsyncMock(), find_one_and_update=AsyncMock(return_value={"count": 1}),
        )
        store = MongoRateLimitStore(collection)
        await store.initialize()
        collection.create_index.assert_awaited_once_with("expires_at", expireAfterSeconds=0, name="rate_limit_expiry")
        await RateLimiter(store, clock=lambda: 120).check(RateLimitPolicy("email", 2, 60), "test@example.com")
        args, kwargs = collection.find_one_and_update.call_args
        self.assertEqual(len(args[0]["_id"]), 64)
        self.assertNotIn("test@example.com", repr(args))
        self.assertEqual(args[1]["$inc"], {"count": 1})
        self.assertEqual(args[1]["$setOnInsert"]["expires_at"], datetime.fromtimestamp(240, timezone.utc))
        self.assertTrue(kwargs["upsert"])

    async def test_concurrent_first_insert_retries_on_the_existing_bucket(self):
        collection = SimpleNamespace(find_one_and_update=AsyncMock(side_effect=[DuplicateKeyError("race"), {"count": 2}]))
        count = await MongoRateLimitStore(collection).hit("test-key", datetime.now(timezone.utc))
        self.assertEqual(count, 2)
        self.assertFalse(collection.find_one_and_update.call_args.kwargs["upsert"])


class RateLimitRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.state.rate_limiter = RateLimiter(AtomicTestStore(), clock=lambda: 120)
        self.app.include_router(auth_router)
        self.app.include_router(blogs_router)
        self.app.include_router(comments_router)
        self.client = TestClient(self.app)

    def test_login_limit_returns_429_even_when_credentials_are_wrong(self):
        with patch("routers.auth.User") as users:
            users.email = "email"
            users.find_one = AsyncMock(return_value=None)
            for _ in range(10):
                self.assertEqual(self.client.post("/auth/login", json={"email": "test@example.com", "password": "wrong"}).status_code, 401)
            response = self.client.post("/auth/login", json={"email": "test@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_account_limit_survives_a_change_of_client_ip(self):
        with patch("routers.auth.User") as users, patch("core.rate_limit.client_ip", side_effect=lambda req: str(req.headers.get("x-test-client", "a"))):
            users.email = "email"
            users.find_one = AsyncMock(return_value=None)
            for i in range(10):
                response = self.client.post("/auth/login", headers={"x-test-client": str(i)}, json={"email": "same@example.com", "password": "wrong"})
                self.assertEqual(response.status_code, 401)
            response = self.client.post("/auth/login", headers={"x-test-client": "next"}, json={"email": "same@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 429)

    def test_registration_limit_applies_to_invalid_payloads(self):
        for _ in range(10):
            self.assertEqual(self.client.post("/auth/register", json={}).status_code, 422)
        self.assertEqual(self.client.post("/auth/register", json={}).status_code, 429)

    def test_blog_and_comment_limits_apply_per_authenticated_user(self):
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)
        # Stop before real writes; the rate dependencies still execute.
        with patch("routers.blogs._resolve_category", new_callable=AsyncMock):
            for _ in range(10):
                self.assertEqual(self.client.post("/blogs", json={}).status_code, 400)
            self.assertEqual(self.client.post("/blogs", json={}).status_code, 429)
        for _ in range(20):
            self.assertEqual(self.client.post(f"/blogs/{CATEGORY_ID}/comments", json={}).status_code, 422)
        self.assertEqual(self.client.post(f"/blogs/{CATEGORY_ID}/comments", json={}).status_code, 429)

    def test_global_write_limit_keeps_get_and_cors_working(self):
        from fastapi.middleware.cors import CORSMiddleware

        self.app.add_middleware(WriteRateLimitMiddleware)
        self.app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], expose_headers=["Retry-After"])

        @self.app.api_route("/probe", methods=["GET", "POST"])
        async def probe():
            return {"ok": True}

        self.client = TestClient(self.app)
        for _ in range(120):
            self.assertEqual(self.client.post("/probe").status_code, 200)
        response = self.client.post("/probe", headers={"Origin": "http://localhost:5173", "X-Forwarded-For": "203.0.113.10"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertEqual(self.client.get("/probe").status_code, 200)
        self.assertEqual(self.client.options("/probe", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}).status_code, 200)


class RoleProvisioningTests(unittest.IsolatedAsyncioTestCase):
    def provision_store(self, matches):
        from unittest.mock import MagicMock

        users = MagicMock()
        users.find.return_value.limit.return_value.to_list = AsyncMock(return_value=matches)
        users.find_one = AsyncMock(return_value=matches[0] if matches else None)
        users.insert_one = AsyncMock()
        users.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
        return users

    async def test_existing_admin_email_keeps_username_and_password(self):
        users = self.provision_store([{"_id": USER_ID, "username": "existing-name", "role": "user"}])
        with TemporaryDirectory() as folder:
            path = Path(folder) / ".env.admin.local"
            result = await provision(users, "test@example.com", "requested name", path, True)
            self.assertEqual(result["username"], "existing-name")
            self.assertFalse(path.exists())
        users.insert_one.assert_not_awaited()
        self.assertNotIn("hashed_password", users.update_one.call_args.args[1]["$set"])

    async def test_new_admin_credentials_are_local_and_not_returned(self):
        users = self.provision_store([])
        with TemporaryDirectory() as folder:
            path = Path(folder) / ".env.admin.local"
            result = await provision(users, "test@example.com", "test owner", path, True)
            password = path.read_text(encoding="utf-8").split("ADMIN_PASSWORD=", 1)[1].strip()
            document = users.insert_one.call_args.args[0]
            self.assertEqual(document["role"], "admin")
            self.assertTrue(security.verify_password(password, document["hashed_password"]))
            self.assertNotIn(password, repr(result))

    async def test_existing_credentials_file_is_not_overwritten(self):
        users = self.provision_store([])
        with TemporaryDirectory() as folder:
            path = Path(folder) / ".env.admin.local"
            path.write_text("existing file", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                await provision(users, "test@example.com", "test owner", path, True)
            self.assertEqual(path.read_text(encoding="utf-8"), "existing file")
        users.insert_one.assert_not_awaited()

    async def test_preview_does_not_write_and_apply_changes_only_the_target(self):
        users = SimpleNamespace(find_one=AsyncMock(return_value={"_id": USER_ID}), update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
        await change_role(users, "owner", "admin", False)
        users.update_one.assert_not_awaited()
        await change_role(users, "owner", "admin", True)
        args = users.update_one.call_args.args
        self.assertEqual(args[0], {"_id": USER_ID})
        self.assertEqual(args[1]["$set"]["role"], "admin")

    async def test_last_admin_cannot_be_demoted(self):
        users = SimpleNamespace(find_one=AsyncMock(return_value={"_id": USER_ID, "role": "admin"}), count_documents=AsyncMock(return_value=1), update_one=AsyncMock())
        with self.assertRaises(ValueError):
            await change_role(users, "owner", "user", True)
        users.update_one.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
