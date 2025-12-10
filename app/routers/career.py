# app/routers/career.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from app.db.database import get_db
from app.dependencies import get_current_user
from app.db.models import User
from app.schemas.career import (
    TestStartRequest, 
    TestSessionResponse, 
    AnswerRequest,
    CareerResultResponse
)
from app.services.career_service import CareerService

router = APIRouter(prefix="/career", tags=["Career Guide (Prof Guid)"])

@router.post("/start", response_model=TestSessionResponse)
async def start_career_test(
    request: TestStartRequest,
    db: AsyncSession = Depends(get_db),
    # Пользователь может быть не авторизован (опционально), но пока оставим
    current_user: User = Depends(get_current_user) 
):
    """Начать новый тест"""
    return await CareerService.start_test(
        user_id=current_user.id,
        difficulty=request.difficulty,
        count=request.questions_count,
        db=db
    )

@router.post("/answer", response_model=Union[TestSessionResponse, CareerResultResponse]) # <--- Важен порядок
async def submit_answer(
    request: AnswerRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await CareerService.process_answer(
        session_id=request.session_id,
        answer_text=request.answer_text,
        db=db
    )
    
    if not result:
        raise HTTPException(404, "Сессия не найдена или завершена")
        
    return result