import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "blog_db")
# Must be a long random secret (e.g. secrets.token_hex(32)). Never commit the real value.
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
# Overridable via env so staging/prod can use a different TTL without code changes.
def positive_int_setting(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return value


ACCESS_TOKEN_EXPIRE_MINUTES = positive_int_setting("ACCESS_TOKEN_EXPIRE_MINUTES", 30)

# Shared MongoDB-backed fixed-window rate limits. Each setting is requests/window.
WRITE_RATE_LIMIT = positive_int_setting("WRITE_RATE_LIMIT", 120)
WRITE_RATE_WINDOW_SECONDS = positive_int_setting("WRITE_RATE_WINDOW_SECONDS", 60)
LOGIN_RATE_LIMIT = positive_int_setting("LOGIN_RATE_LIMIT", 10)
LOGIN_RATE_WINDOW_SECONDS = positive_int_setting("LOGIN_RATE_WINDOW_SECONDS", 60)
LOGIN_ACCOUNT_RATE_LIMIT = positive_int_setting("LOGIN_ACCOUNT_RATE_LIMIT", 10)
LOGIN_ACCOUNT_RATE_WINDOW_SECONDS = positive_int_setting("LOGIN_ACCOUNT_RATE_WINDOW_SECONDS", 300)
REGISTER_RATE_LIMIT = positive_int_setting("REGISTER_RATE_LIMIT", 10)
REGISTER_RATE_WINDOW_SECONDS = positive_int_setting("REGISTER_RATE_WINDOW_SECONDS", 3600)
BLOG_RATE_LIMIT = positive_int_setting("BLOG_RATE_LIMIT", 10)
BLOG_RATE_WINDOW_SECONDS = positive_int_setting("BLOG_RATE_WINDOW_SECONDS", 60)
COMMENT_RATE_LIMIT = positive_int_setting("COMMENT_RATE_LIMIT", 20)
COMMENT_RATE_WINDOW_SECONDS = positive_int_setting("COMMENT_RATE_WINDOW_SECONDS", 60)

# Virgülle ayrılmış frontend adresleri. Yerel önizlemede Vite dolu porttan bir
# sonrakine geçebildiği için birden fazla origin desteklenir.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

# File upload settings — all overridable via environment variables.
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))
ALLOWED_IMAGE_TYPES = {
    "image/jpeg", 
    "image/jpg", 
    "image/png", 
    "image/webp", 
    "image/pjpeg", 
    "image/x-png"
}
