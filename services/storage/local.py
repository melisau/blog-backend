import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from core.config import UPLOAD_DIR
from services.storage.base import StorageService


class LocalStorageService(StorageService):
    """
    Dosyaları sunucunun yerel diskine kaydeden StorageService implementasyonu.
    UPLOAD_DIR config değişkeni üzerinden kök dizin belirlenebilir.
    """

    def __init__(self, base_dir: str = UPLOAD_DIR) -> None:
        self._base_dir = base_dir

    async def save_file(self, file: UploadFile, subfolder: str) -> str:
        target_dir = Path(self._base_dir) / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        extension = Path(file.filename or "file").suffix.lower()
        filename = f"{uuid.uuid4()}{extension}"
        file_path = target_dir / filename

        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        # "/" ile birleştirerek OS bağımsız public URL üret.
        return f"/{UPLOAD_DIR}/{subfolder}/{filename}"

    async def delete_file(self, url: str) -> None:
        # "/uploads/blogs/abc.jpg" → "uploads/blogs/abc.jpg" → fiziksel yol
        relative = url.lstrip("/")
        file_path = Path(relative)
        if file_path.exists():
            file_path.unlink()
