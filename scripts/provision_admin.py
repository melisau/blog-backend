"""Find an admin by email or explicitly create one with private local credentials."""

import argparse
import asyncio
import json
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import EmailStr, TypeAdapter
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from core.config import MONGODB_DB_NAME, MONGODB_URL
from core.roles import UserRole
from core.security import hash_password
from models.user import User
from schemas.user import UserCreate
from scripts.set_user_role import change_role


async def provision(users, email: str, username: str, credentials_file: Path, apply: bool):
    email = str(TypeAdapter(EmailStr).validate_python(email))
    matches = await users.find(
        {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
    ).limit(2).to_list(length=2)
    if len(matches) > 1:
        raise ValueError("Bu e-posta için birden fazla hesap var; önce hesapları inceleyin.")
    if matches:
        existing = matches[0]
        message = await change_role(users, existing["username"], UserRole.ADMIN.value, apply)
        return {"action": "existing", "username": existing["username"], "message": message}
    if await users.find_one({"username": username}):
        raise ValueError("İstenen kullanıcı adı başka bir hesaba ait; yeni hesap oluşturulmadı.")
    if not apply:
        return {"action": "preview-create", "username": username, "email": email}

    password = secrets.token_urlsafe(24)
    payload = UserCreate(username=username, email=email, password=password)
    # model_construct avoids connecting Beanie to the database or running seeds.
    user = User.model_construct(
        username=payload.username,
        email=str(payload.email),
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
    )
    document = user.model_dump(exclude={"id"})
    credentials_file = credentials_file.resolve()
    # Exclusive creation: never overwrite another account's credential file.
    # Keep this file if Mongo returns an ambiguous network error after insertion.
    with credentials_file.open("x", encoding="utf-8") as handle:
        handle.write(
            "# Yerel yönetici giriş bilgileri. Git'e eklemeyin veya paylaşmayın.\n"
            f"ADMIN_EMAIL={email}\nADMIN_USERNAME={username}\nADMIN_PASSWORD={password}\n",
        )
    await users.insert_one(document)
    return {"action": "created", "username": username, "email": email, "role": "admin", "credentials_file": str(credentials_file)}


async def run(args):
    if not MONGODB_URL:
        raise ValueError("MONGODB_URL ayarlanmalı.")
    client = AsyncMongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    try:
        return await provision(
            client[MONGODB_DB_NAME]["users"], args.email, args.username,
            Path(args.credentials_file), args.apply,
        )
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True, help="Yalnızca yeni hesap için kullanıcı adı")
    parser.add_argument("--credentials-file", default=str(ROOT / ".env.admin.local"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args)), ensure_ascii=False))
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except FileExistsError:
        parser.exit(1, "Giriş bilgileri dosyası zaten var; üzerine yazılmadı.\n")
    except PyMongoError:
        parser.exit(1, "Veritabanı işlem sonucu doğrulanamadı; varsa oluşturulan giriş dosyası korundu.\n")
