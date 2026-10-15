"""Explicit local admin provisioning; read-only unless --apply is supplied."""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from core.config import MONGODB_DB_NAME, MONGODB_URL
from core.roles import UserRole


async def change_role(users, username: str, role: str, apply: bool) -> str:
    user = await users.find_one({"username": username})
    if user is None:
        raise ValueError("Kullanıcı bulunamadı; yeni hesap oluşturulmadı.")
    current_role = user.get("role", UserRole.USER.value)
    summary = f"{username}: {current_role} -> {role}"
    if not apply:
        return f"Önizleme: {summary}. Kaydetmek için --apply ekleyin."
    if current_role == role:
        return f"Değişiklik yok: {summary}"
    if current_role == UserRole.ADMIN and role == UserRole.USER:
        if await users.count_documents({"role": UserRole.ADMIN.value}) <= 1:
            raise ValueError("Son yöneticinin yetkisi kaldırılamaz; önce başka bir yönetici atayın.")
    result = await users.update_one(
        {"_id": user["_id"]},
        {"$set": {"role": role, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count != 1:
        raise ValueError("Kullanıcı artık mevcut değil; rol değiştirilemedi.")
    return f"Kaydedildi: {summary}"


async def run(args) -> str:
    if not MONGODB_URL:
        raise ValueError("MONGODB_URL ayarlanmalı.")
    client = AsyncMongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    try:
        return await change_role(
            client[MONGODB_DB_NAME]["users"], args.username, args.role, args.apply,
        )
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="Mevcut hesabın tam kullanıcı adı")
    parser.add_argument("--role", required=True, choices=[role.value for role in UserRole])
    parser.add_argument("--apply", action="store_true", help="Rol değişikliğini gerçekten kaydet")
    args = parser.parse_args()
    try:
        print(asyncio.run(run(args)))
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except PyMongoError:
        parser.exit(1, "Veritabanına erişilemedi; bağlantı ve izinleri kontrol edin.\n")
