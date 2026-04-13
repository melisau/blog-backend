from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from core.config import JWT_ALGORITHM, JWT_SECRET
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
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # sub holds the user's string ID set at token creation time.
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        # Catches expired tokens, bad signatures, and malformed payloads uniformly.
        raise credentials_exception

    user = await User.get(user_id)
    if user is None:
        # Token was valid but the account was deleted after it was issued.
        raise credentials_exception

    return user
