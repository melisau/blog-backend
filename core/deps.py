from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from beanie import PydanticObjectId
from bson.errors import InvalidId
from jose import JWTError

from core.roles import UserRole
from core.security import decode_access_token
from models.user import User

# Points to the login endpoint so FastAPI's OpenAPI UI can auto-fill the token form.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        # WWW-Authenticate header is required by the OAuth2 Bearer spec (RFC 6750).
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id = PydanticObjectId(decode_access_token(token))
    except (JWTError, ValueError, TypeError, InvalidId):
        # Catches expired tokens, bad signatures, and malformed payloads uniformly.
        raise credentials_exception

    user = await User.get(user_id)
    if user is None:
        # Token was valid but the account was deleted after it was issued.
        raise credentials_exception

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    # Always use the current database role, not a JWT or client-provided role.
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için yönetici yetkisi gerekiyor.",
        )
    return current_user
