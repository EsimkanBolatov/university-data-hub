# app/routers/ai.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from app.db.database import get_db
from app.services.ai_service import AIService
from app.dependencies import get_current_user
from app.db.models import User

router = APIRouter(prefix="/ai", tags=["AI Module"])

# --- Схемы данных ---
class RecommendRequest(BaseModel):
    score: int
    city: Optional[str] = None
    budget: Optional[int] = None
    interests: str  # например: "хочу программировать игры"

class ChatRequest(BaseModel):
    question: str

class CompareRequest(BaseModel):
    university_ids: List[int]

# --- Эндпоинты ---

@router.post("/sync")
async def sync_knowledge_base(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """(Admin) Обновить знания ИИ из базы данных"""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can sync AI")
    
    result = await AIService.sync_database_to_vector_db(db)
    return result

@router.post("/recommend")
async def ai_recommend(
    req: RecommendRequest,
    db: AsyncSession = Depends(get_db)
):
    """Получить AI рекомендации на основе баллов и интересов"""
    return await AIService.get_recommendations(req.model_dump(), db)

@router.post("/compare")
async def ai_compare(
    req: CompareRequest,
    db: AsyncSession = Depends(get_db)
):
    """Умное сравнение вузов с текстовым выводом"""
    return {"analysis": await AIService.compare_universities(req.university_ids, db)}

@router.post("/chat")
async def ai_chat(req: ChatRequest):
    """Чат-бот с контекстом (RAG)"""
    answer = await AIService.chat_rag(req.question)
    return {"answer": answer}

@router.post("/admin/structure-text")
async def structure_text(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """(Admin) Распознать текст из файла и превратить в JSON"""
    if current_user.role != "admin":
        raise HTTPException(403, "Access denied")
    
    content = await file.read()
    # Тут можно добавить логику pypdf/python-docx для извлечения текста
    # Для MVP предположим, что это текстовый файл
    text = content.decode("utf-8")
    
    return await AIService.parse_unstructured_text(text)