"""Opt-in real Mongo tests; each test owns one disposable, uniquely named collection."""

import asyncio
import os
import time
import unittest
from uuid import uuid4

from fastapi import HTTPException
from pymongo import AsyncMongoClient

from core.config import MONGODB_DB_NAME, MONGODB_URL
from core.rate_limit import MongoRateLimitStore, RateLimitPolicy, RateLimiter


@unittest.skipUnless(os.getenv("RUN_MONGO_TESTS") == "1", "Set RUN_MONGO_TESTS=1 for an isolated MongoDB integration test")
class MongoRateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = AsyncMongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        self.addAsyncCleanup(self.client.close)
        await self.client.admin.command("ping")
        self.owned_name = "security_test_limits_" + uuid4().hex
        self.collection = await self.client[MONGODB_DB_NAME].create_collection(self.owned_name)
        self.addAsyncCleanup(self.drop_owned_collection)
        self.store = MongoRateLimitStore(self.collection)
        await self.store.initialize()
        # Future, deterministic window; the server TTL thread cannot expire it
        # while the test is still exercising concurrency and boundary behavior.
        self.now = (int(time.time()) // 60 + 1) * 60

    async def drop_owned_collection(self):
        if self.collection.name != self.owned_name or not self.owned_name.startswith("security_test_limits_"):
            raise RuntimeError("Refusing to delete a collection not owned by this test.")
        await self.collection.drop()

    async def test_real_atomic_counter_is_shared_between_workers(self):
        workers = [RateLimiter(MongoRateLimitStore(self.collection), clock=lambda: self.now) for _ in range(3)]
        policy = RateLimitPolicy("mongo-shared", 7, 60)
        results = await asyncio.gather(
            *(workers[i % 3].check(policy, "test-user") for i in range(40)),
            return_exceptions=True,
        )
        self.assertEqual(sum(result is None for result in results), 7)
        self.assertEqual(sum(isinstance(result, HTTPException) and result.status_code == 429 for result in results), 33)
        bucket = await self.collection.find_one({})
        self.assertEqual(bucket["count"], 40)
        self.assertEqual(await self.collection.count_documents({}), 1)

    async def test_real_window_reset_does_not_wait_for_ttl_deletion(self):
        limiter = RateLimiter(self.store, clock=lambda: self.now)
        policy = RateLimitPolicy("mongo-reset", 1, 60)
        await limiter.check(policy, "test-user")
        with self.assertRaises(HTTPException):
            await limiter.check(policy, "test-user")
        self.now += 60
        await limiter.check(policy, "test-user")
        self.assertEqual(await self.collection.count_documents({}), 2)
        indexes = await self.collection.index_information()
        self.assertEqual(indexes["rate_limit_expiry"]["expireAfterSeconds"], 0)
