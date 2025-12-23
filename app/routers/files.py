"""
API роутер для загрузки файлов
app/routers/files.py
"""
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel

from app.db.database import get_db
from app.dependencies import get_current_user
from app.db.models import User
from app.services.file_storage_service import FileStorageService, FileValidators

router = APIRouter(prefix="/files", tags=["File Upload"])


# ============= СХЕМЫ =============

class FileUploadResponse(BaseModel):
    """Ответ после загрузки файла"""
    url: str
    filename: str
    original_filename: str
    size: int
    content_type: str
    folder: str
    uploaded_at: str


class FileDeleteRequest(BaseModel):
    """Запрос на удаление файла"""
    file_url: str


# ============= ЗАГРУЗКА ФАЙЛОВ =============

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    folder: str = Query("general", regex="^(general|challenges|materials|avatars|documents)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Универсальная загрузка файла
    
    Папки:
    - general: общие файлы
    - challenges: решения челленджей
    - materials: учебные материалы
    - avatars: аватары пользователей
    - documents: документы (PDF, DOCX)
    """
    
    # Читаем файл
    file_data = await file.read()
    
    # Базовая валидация (макс 100MB)
    storage = FileStorageService()
    validation = storage.validate_file(
        file.filename,
        len(file_data),
        max_size_mb=100
    )
    
    if not validation["valid"]:
        raise HTTPException(400, validation["error"])
    
    # Загружаем
    result = await storage.upload_file(
        file_data,
        file.filename,
        folder=folder,
        content_type=file.content_type
    )
    
    return FileUploadResponse(**result)


@router.post("/upload/image", response_model=FileUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    folder: str = Query("materials", regex="^(challenges|materials|avatars)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузка изображения (с валидацией)
    
    Допустимые форматы: JPG, PNG, GIF, WebP
    Максимальный размер: 5 MB
    """
    
    file_data = await file.read()
    
    # Строгая валидация для изображений
    validation = FileValidators.image_validator(file.filename, len(file_data))
    if not validation["valid"]:
        raise HTTPException(400, validation["error"])
    
    storage = FileStorageService()
    result = await storage.upload_file(
        file_data,
        file.filename,
        folder=folder,
        content_type=file.content_type
    )
    
    return FileUploadResponse(**result)


@router.post("/upload/document", response_model=FileUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    folder: str = Query("documents"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузка документа
    
    Допустимые форматы: PDF, DOC, DOCX, TXT
    Максимальный размер: 10 MB
    """
    
    file_data = await file.read()
    
    validation = FileValidators.document_validator(file.filename, len(file_data))
    if not validation["valid"]:
        raise HTTPException(400, validation["error"])
    
    storage = FileStorageService()
    result = await storage.upload_file(
        file_data,
        file.filename,
        folder=folder,
        content_type=file.content_type
    )
    
    return FileUploadResponse(**result)


@router.post("/upload/code", response_model=FileUploadResponse)
async def upload_code(
    file: UploadFile = File(...),
    folder: str = Query("materials"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузка кода
    
    Допустимые форматы: .py, .js, .ts, .cpp, .java, .go
    Максимальный размер: 1 MB
    """
    
    file_data = await file.read()
    
    validation = FileValidators.code_validator(file.filename, len(file_data))
    if not validation["valid"]:
        raise HTTPException(400, validation["error"])
    
    storage = FileStorageService()
    result = await storage.upload_file(
        file_data,
        file.filename,
        folder=folder,
        content_type=file.content_type or "text/plain"
    )
    
    return FileUploadResponse(**result)


@router.post("/upload/3d-model", response_model=FileUploadResponse)
async def upload_3d_model(
    file: UploadFile = File(...),
    folder: str = Query("materials"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузка 3D модели
    
    Допустимые форматы: .obj, .fbx, .glb, .gltf, .stl, .blend
    Максимальный размер: 50 MB
    """
    
    file_data = await file.read()
    
    validation = FileValidators.model_3d_validator(file.filename, len(file_data))
    if not validation["valid"]:
        raise HTTPException(400, validation["error"])
    
    storage = FileStorageService()
    result = await storage.upload_file(
        file_data,
        file.filename,
        folder=folder,
        content_type=file.content_type or "application/octet-stream"
    )
    
    return FileUploadResponse(**result)


@router.post("/upload/archive", response_model=FileUploadResponse)
async def upload_archive(
    file: UploadFile = File(...),
    folder: str = Query("challenges"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузка архива (для решений челленджей)
    
    Допустимые форматы: .zip, .rar, .7z, .tar, .gz
    Максимальный размер: 100 MB
    """
    
    file_data = await file.read()
    
    validation = FileValidators.archive_validator(file.filename, len(file_data))
    if not validation["valid"]:
        raise HTTPException(400, validation["error"])
    
    storage = FileStorageService()
    result = await storage.upload_file(
        file_data,
        file.filename,
        folder=folder,
        content_type=file.content_type or "application/zip"
    )
    
    return FileUploadResponse(**result)


@router.post("/upload/multiple", response_model=List[FileUploadResponse])
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    folder: str = Query("general"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузка нескольких файлов одновременно
    
    Максимум: 10 файлов за раз
    """
    
    if len(files) > 10:
        raise HTTPException(400, "Максимум 10 файлов за раз")
    
    storage = FileStorageService()
    results = []
    
    for file in files:
        file_data = await file.read()
        
        # Базовая валидация
        validation = storage.validate_file(
            file.filename,
            len(file_data),
            max_size_mb=50
        )
        
        if not validation["valid"]:
            results.append({
                "error": validation["error"],
                "filename": file.filename
            })
            continue
        
        # Загрузка
        try:
            result = await storage.upload_file(
                file_data,
                file.filename,
                folder=folder,
                content_type=file.content_type
            )
            results.append(result)
        except Exception as e:
            results.append({
                "error": str(e),
                "filename": file.filename
            })
    
    return results


# ============= УДАЛЕНИЕ ФАЙЛОВ =============

@router.delete("/delete")
async def delete_file(
    request: FileDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить файл
    
    Требуется URL файла
    """
    
    storage = FileStorageService()
    success = await storage.delete_file(request.file_url)
    
    if not success:
        raise HTTPException(404, "Файл не найден или уже удалён")
    
    return {
        "message": "Файл успешно удалён",
        "url": request.file_url
    }


# ============= PRESIGNED URLs (S3 only) =============

@router.get("/presigned-url")
async def get_presigned_url(
    file_path: str = Query(..., description="Путь к файлу в S3"),
    expiration: int = Query(3600, ge=60, le=604800, description="Время жизни в секундах"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить временную ссылку для скачивания (S3/MinIO)
    
    Параметры:
    - file_path: путь к файлу (например: "challenges/uuid.zip")
    - expiration: время жизни ссылки в секундах (по умолчанию 1 час)
    """
    
    storage = FileStorageService()
    
    if storage.storage_type == "local":
        raise HTTPException(400, "Presigned URLs доступны только для S3/MinIO")
    
    try:
        presigned_url = await storage.generate_presigned_url(
            file_path,
            expiration
        )
        
        return {
            "url": presigned_url,
            "expires_in": expiration,
            "expires_at": (datetime.utcnow() + timedelta(seconds=expiration)).isoformat()
        }
    except Exception as e:
        raise HTTPException(500, f"Ошибка генерации ссылки: {str(e)}")


# ============= ИНФОРМАЦИЯ О ХРАНИЛИЩЕ =============

@router.get("/storage-info")
async def get_storage_info(
    current_user: User = Depends(get_current_user)
):
    """Информация о текущем хранилище"""
    
    storage = FileStorageService()
    
    info = {
        "storage_type": storage.storage_type,
        "max_file_size_mb": {
            "image": 5,
            "document": 10,
            "code": 1,
            "3d_model": 50,
            "archive": 100,
            "general": 100
        },
        "allowed_extensions": {
            "image": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
            "document": [".pdf", ".doc", ".docx", ".txt"],
            "code": [".py", ".js", ".jsx", ".ts", ".tsx", ".cpp", ".c", ".java", ".go"],
            "3d_model": [".obj", ".fbx", ".glb", ".gltf", ".stl", ".blend"],
            "archive": [".zip", ".rar", ".7z", ".tar", ".gz"]
        }
    }
    
    if storage.storage_type in ["s3", "minio"]:
        info["bucket_name"] = storage.bucket_name
        info["endpoint"] = os.getenv("S3_ENDPOINT_URL", "AWS S3")
    else:
        info["local_path"] = str(storage.local_storage_path)
    
    return info


# ============= СТАТИКА (для local storage) =============
