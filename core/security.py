from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET


def hash_password(plain: str) -> str:
    # bcrypt operates on bytes; .decode() stores the result as a plain str in MongoDB.
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    # checkpw uses constant-time comparison to prevent timing attacks.
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str) -> str:
    # timezone.utc is required; naive datetimes cause incorrect expiry comparisons in jose.
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # "sub" is the standard JWT claim for the principal identity (RFC 7519).
    payload = {"sub": subject, "iat": issued_at, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={"require_sub": True, "require_exp": True, "require_iat": True},
    )
    issued_at, expires_at = payload["iat"], payload["exp"]
    if type(issued_at) is not int or type(expires_at) is not int:
        raise JWTError("Invalid token timestamps.")
    max_lifetime = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    if not 0 < expires_at - issued_at <= max_lifetime:
        raise JWTError("Invalid token lifetime.")
    if issued_at > datetime.now(timezone.utc).timestamp() + 5:
        raise JWTError("Token issued in the future.")
    return payload["sub"]
