from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.dependencies import get_current_user
from app.db.models import User
import tempfile
from pathlib import Path
from scripts.import_json import import_university_from_json

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/upload-json")
async def upload_university_json(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Загрузка JSON файла университета (только для админов)"""
    
    if current_user.role != "admin":
        return {"error": "Доступ запрещен"}
    
    # Сохраняем во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
    
    try:
        await import_university_from_json(tmp_path, db)
        return {"status": "success", "message": f"Файл {file.filename} успешно обработан"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        tmp_path.unlink()  # Удаляем временный файл