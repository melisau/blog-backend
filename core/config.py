import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "blog_db")
# Must be a long random secret (e.g. secrets.token_hex(32)). Never commit the real value.
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
# Overridable via env so staging/prod can use a different TTL without code changes.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

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
