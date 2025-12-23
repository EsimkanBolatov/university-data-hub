"""
Сервис хранения файлов (S3-совместимый)
app/services/file_storage_service.py

Поддержка:
- AWS S3
- MinIO (self-hosted)
- Local storage (для разработки)

Типы файлов:
- Изображения (чертежи, скриншоты)
- 3D модели (.obj, .fbx, .glb)
- Код (.py, .js, .cpp)
- Документы (.pdf, .docx)
- Видео (ссылки на YouTube/Vimeo)
"""
import os
import uuid
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
import mimetypes

try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False


class FileStorageService:
    """Универсальный сервис хранения файлов"""
    
    def __init__(self):
        self.storage_type = os.getenv("STORAGE_TYPE", "local")  # local, s3, minio
        
        if self.storage_type in ["s3", "minio"]:
            if not S3_AVAILABLE:
                raise ImportError("boto3 не установлен. Запустите: pip install boto3")
            
            self.s3_client = boto3.client(
                's3',
                endpoint_url=os.getenv("S3_ENDPOINT_URL"),  # Для MinIO
                aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
                region_name=os.getenv("S3_REGION", "us-east-1")
            )
            self.bucket_name = os.getenv("S3_BUCKET_NAME", "skill-tree-files")
        else:
            # Local storage
            self.local_storage_path = Path(os.getenv("LOCAL_STORAGE_PATH", "./uploads"))
            self.local_storage_path.mkdir(exist_ok=True, parents=True)
    
    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        folder: str = "general",
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Загрузить файл
        
        Args:
            file_data: Байты файла
            filename: Оригинальное имя файла
            folder: Папка для организации (materials, challenges, avatars)
            content_type: MIME тип (определится автоматически если None)
        
        Returns:
            {
                "url": "https://...",
                "filename": "uuid_filename.ext",
                "size": 1024,
                "content_type": "image/png"
            }
        """
        
        # Генерируем уникальное имя
        file_ext = Path(filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = f"{folder}/{unique_filename}"
        
        # Определяем MIME тип
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = "application/octet-stream"
        
        file_size = len(file_data)
        
        if self.storage_type in ["s3", "minio"]:
            url = await self._upload_to_s3(file_data, file_path, content_type)
        else:
            url = await self._upload_local(file_data, file_path)
        
        return {
            "url": url,
            "filename": unique_filename,
            "original_filename": filename,
            "size": file_size,
            "content_type": content_type,
            "folder": folder,
            "uploaded_at": datetime.utcnow().isoformat()
        }
    
    async def _upload_to_s3(
        self,
        file_data: bytes,
        file_path: str,
        content_type: str
    ) -> str:
        """Загрузка в S3/MinIO"""
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_data,
                ContentType=content_type,
                ACL='public-read'  # Публичный доступ
            )
            
            # Генерируем URL
            if self.storage_type == "minio":
                # MinIO URL
                endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
                url = f"{endpoint}/{self.bucket_name}/{file_path}"
            else:
                # AWS S3 URL
                region = os.getenv("S3_REGION", "us-east-1")
                url = f"https://{self.bucket_name}.s3.{region}.amazonaws.com/{file_path}"
            
            return url
            
        except ClientError as e:
            raise Exception(f"Ошибка загрузки в S3: {e}")
    
    async def _upload_local(self, file_data: bytes, file_path: str) -> str:
        """Загрузка в локальное хранилище"""
        
        full_path = self.local_storage_path / file_path
        full_path.parent.mkdir(exist_ok=True, parents=True)
        
        with open(full_path, "wb") as f:
            f.write(file_data)
        
        # Возвращаем относительный URL
        base_url = os.getenv("BASE_URL", "http://localhost:8080")
        return f"{base_url}/uploads/{file_path}"
    
    async def delete_file(self, file_url: str) -> bool:
        """Удалить файл по URL"""
        
        if self.storage_type in ["s3", "minio"]:
            # Извлекаем ключ из URL
            file_key = file_url.split(f"{self.bucket_name}/")[-1]
            
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
                return True
            except ClientError:
                return False
        else:
            # Local storage
            file_path = file_url.split("/uploads/")[-1]
            full_path = self.local_storage_path / file_path
            
            if full_path.exists():
                full_path.unlink()
                return True
            return False
    
    async def generate_presigned_url(
        self,
        file_path: str,
        expiration: int = 3600
    ) -> str:
        """
        Генерировать временную ссылку для скачивания (S3 only)
        
        Args:
            file_path: Путь к файлу в S3
            expiration: Время жизни ссылки в секундах (по умолчанию 1 час)
        """
        
        if self.storage_type not in ["s3", "minio"]:
            raise Exception("Presigned URLs доступны только для S3/MinIO")
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_path
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            raise Exception(f"Ошибка генерации presigned URL: {e}")
    
    def validate_file(
        self,
        filename: str,
        file_size: int,
        allowed_extensions: list = None,
        max_size_mb: int = 10
    ) -> Dict[str, Any]:
        """
        Валидация файла перед загрузкой
        
        Returns:
            {"valid": True/False, "error": "..."}
        """
        
        # Проверка расширения
        if allowed_extensions:
            file_ext = Path(filename).suffix.lower()
            if file_ext not in allowed_extensions:
                return {
                    "valid": False,
                    "error": f"Недопустимое расширение. Разрешены: {', '.join(allowed_extensions)}"
                }
        
        # Проверка размера
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return {
                "valid": False,
                "error": f"Файл слишком большой. Максимум: {max_size_mb} MB"
            }
        
        # Проверка имени (безопасность)
        if ".." in filename or "/" in filename or "\\" in filename:
            return {
                "valid": False,
                "error": "Недопустимые символы в имени файла"
            }
        
        return {"valid": True}


# ============= ВАЛИДАТОРЫ ДЛЯ РАЗНЫХ ТИПОВ ФАЙЛОВ =============

class FileValidators:
    """Предустановленные валидаторы"""
    
    @staticmethod
    def image_validator(filename: str, file_size: int) -> Dict[str, Any]:
        """Валидация изображений"""
        storage = FileStorageService()
        return storage.validate_file(
            filename,
            file_size,
            allowed_extensions=[".jpg", ".jpeg", ".png", ".gif", ".webp"],
            max_size_mb=5
        )
    
    @staticmethod
    def document_validator(filename: str, file_size: int) -> Dict[str, Any]:
        """Валидация документов"""
        storage = FileStorageService()
        return storage.validate_file(
            filename,
            file_size,
            allowed_extensions=[".pdf", ".doc", ".docx", ".txt"],
            max_size_mb=10
        )
    
    @staticmethod
    def code_validator(filename: str, file_size: int) -> Dict[str, Any]:
        """Валидация кода"""
        storage = FileStorageService()
        return storage.validate_file(
            filename,
            file_size,
            allowed_extensions=[".py", ".js", ".jsx", ".ts", ".tsx", ".cpp", ".c", ".java", ".go"],
            max_size_mb=1
        )
    
    @staticmethod
    def model_3d_validator(filename: str, file_size: int) -> Dict[str, Any]:
        """Валидация 3D моделей"""
        storage = FileStorageService()
        return storage.validate_file(
            filename,
            file_size,
            allowed_extensions=[".obj", ".fbx", ".glb", ".gltf", ".stl", ".blend"],
            max_size_mb=50
        )
    
    @staticmethod
    def archive_validator(filename: str, file_size: int) -> Dict[str, Any]:
        """Валидация архивов"""
        storage = FileStorageService()
        return storage.validate_file(
            filename,
            file_size,
            allowed_extensions=[".zip", ".rar", ".7z", ".tar", ".gz"],
            max_size_mb=100
        )


# ============= ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ =============

"""
# В .env файле:
STORAGE_TYPE=minio  # или s3, или local
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=skill-tree-files
S3_REGION=us-east-1

# В роутере:
from fastapi import UploadFile, File
from app.services.file_storage_service import FileStorageService, FileValidators

@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Читаем файл
    file_data = await file.read()
    
    # Валидация
    validation = FileValidators.image_validator(file.filename, len(file_data))
    if not validation["valid"]:
        raise HTTPException(400, validation["error"])
    
    # Загрузка
    storage = FileStorageService()
    result = await storage.upload_file(
        file_data,
        file.filename,
        folder="challenges",
        content_type=file.content_type
    )
    
    return result

# Результат:
{
    "url": "http://localhost:9000/skill-tree-files/challenges/uuid.png",
    "filename": "uuid.png",
    "original_filename": "my_blueprint.png",
    "size": 204800,
    "content_type": "image/png",
    "folder": "challenges",
    "uploaded_at": "2024-12-24T10:30:00"
}
"""