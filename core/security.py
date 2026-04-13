from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET


def hash_password(plain: str) -> str:
    # bcrypt operates on bytes; .decode() stores the result as a plain str in MongoDB.
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    # checkpw uses constant-time comparison to prevent timing attacks.
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str) -> str:
    # timezone.utc is required; naive datetimes cause incorrect expiry comparisons in jose.
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # "sub" is the standard JWT claim for the principal identity (RFC 7519).
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
