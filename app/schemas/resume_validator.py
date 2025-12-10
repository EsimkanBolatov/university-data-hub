# app/schemas/resume_validator.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ResumeUploadResponse(BaseModel):
    """Ответ после загрузки резюме"""
    session_id: int
    parsed_resume: dict
    suspicious_areas: List[str]
    target_profession: str
    difficulty: str


class InterviewQuestion(BaseModel):
    """Вопрос интервью"""
    question_id: int
    question_text: str
    time_limit_seconds: int
    category: str  # technical, behavioral, situational


class InterviewAnswerRequest(BaseModel):
    """Запрос с ответом на вопрос"""
    session_id: int
    question_id: int
    answer_text: str
    time_taken_seconds: int


class InterviewAnswerResponse(BaseModel):
    """Ответ после проверки ответа"""
    is_correct: bool
    confidence_score: float  # 0-100
    feedback: str
    next_question: Optional[InterviewQuestion] = None
    is_interview_complete: bool = False


class SkillVerification(BaseModel):
    """Верификация навыка"""
    skill_name: str
    claimed_level: str  # junior, middle, senior
    verified_level: str
    is_confirmed: bool
    evidence: str


class FinalVerdict(BaseModel):
    """Финальный вердикт"""
    session_id: int
    readiness_score: int  # 0-100
    target_profession: str
    verified_skills: List[SkillVerification]
    unverified_skills: List[str]
    roadmap: List[dict]  # [{topic, resources, priority}]
    recommended_courses: List[str]
    estimated_time_to_ready: str  # "2-3 месяца"
    overall_assessment: str


class StartInterviewRequest(BaseModel):
    """Запрос на старт интервью"""
    target_profession: str = Field(..., description="Целевая профессия")
    difficulty: str = Field("middle", pattern="^(junior|middle|senior)$")
    resume_text: Optional[str] = Field(None, description="Текст резюме (опционально)")