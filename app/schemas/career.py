# app/schemas/career.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.schemas.university import UniversityListResponse

class TestStartRequest(BaseModel):
    difficulty: str = Field(..., pattern="^(easy|medium|hard)$")
    questions_count: int = Field(..., ge=5, le=20)

class TestSessionResponse(BaseModel):
    session_id: int
    current_step: int
    total_steps: int
    question: str
    is_finished: bool = False

class AnswerRequest(BaseModel):
    session_id: int
    answer_text: str

# --- НОВАЯ МОДЕЛЬ ДЛЯ ПРОФЕССИИ ---
class ProfessionItem(BaseModel):
    name: str
    reason: str
    keywords: List[str] = [] # Теперь это список строк, а не просто строка

class CareerResultResponse(BaseModel):
    session_id: int
    is_finished: bool = True  
    analysis: str
    suggested_professions: List[ProfessionItem]
    recommended_universities: List[UniversityListResponse]