# app/routers/ai.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional

from app.db.database import get_db
from app.services.ai_service import AIService
from app.dependencies import get_current_user
from app.db.models import User

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


# --- Схемы ---
class RecommendRequest(BaseModel):
    score: int = Field(..., ge=0, le=140, description="Баллы ЕНТ")
    city: Optional[str] = Field(None, description="Предпочитаемый город")
    budget: Optional[int] = Field(None, ge=0, description="Бюджет в тенге/год")
    interests: str = Field(..., description="Интересы и предпочтения")
    has_dormitory: Optional[bool] = Field(None, description="Нужно ли общежитие")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Вопрос ассистенту")


class CompareRequest(BaseModel):
    university_ids: List[int] = Field(..., min_items=2, max_items=5)


# --- Эндпоинты ---

@router.post("/sync")
async def sync_knowledge_base(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Синхронизация векторной базы знаний
    Доступно только администраторам
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Только администраторы могут синхронизировать базу")

    result = await AIService.sync_database_to_vector_db(db)
    return result


@router.post("/recommend")
async def ai_recommend(
        req: RecommendRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Получить персональные рекомендации университетов
    На основе баллов, бюджета и интересов
    """
    result = await AIService.get_recommendations(req.model_dump(), db)
    return result


@router.post("/compare")
async def ai_compare(
        req: CompareRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Интеллектуальное сравнение университетов
    Анализ по всем параметрам с текстовым выводом
    """
    result = await AIService.compare_universities(req.university_ids, db)
    return result


@router.post("/chat")
async def ai_chat(
        req: ChatRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Чат-бот ассистент с поддержкой RAG
    Отвечает на вопросы о университетах на основе БД и интернета
    """
    result = await AIService.chat_rag(req.question, db)
    return result


@router.post("/admin/parse-text")
async def structure_text(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Распознать и структурировать текст из файла
    Доступно только администраторам
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Доступ запрещён")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except:
        raise HTTPException(400, "Не удалось прочитать файл как текст")

    result = await AIService.parse_unstructured_text(text)
    return result