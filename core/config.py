import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "blog_db")

