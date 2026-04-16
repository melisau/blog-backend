from abc import ABC, abstractmethod

from fastapi import UploadFile


class StorageService(ABC):
    """
    Dosya depolama için soyut arayüz.
    Yerel disk, S3, GCS gibi farklı backend'lere geçişte sadece bu arayüzün
    yeni bir implementasyonu yazılır; router ve model kodu değişmez.
    """

    @abstractmethod
    async def save_file(self, file: UploadFile, subfolder: str) -> str:
        """
        Dosyayı belirtilen alt klasöre kaydeder.
        Dönüş değeri, frontend'in doğrudan kullanabileceği public URL yoludur.
        Örnek: "/uploads/blogs/3f8a2c1d-uuid.jpg"
        """
        ...

    @abstractmethod
    async def delete_file(self, url: str) -> None:
        """
        Verilen public URL yoluna karşılık gelen dosyayı siler.
        Dosya bulunamazsa sessizce geçer.
        """
        ...
