"""
Pydantic схемы для Skill Tree API
app/schemas/skill.py
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============= SKILL (Навыки) =============

class SkillBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_global: bool = False
    specialty_id: Optional[int] = None
    level: int = Field(1, ge=1, le=5)
    estimated_hours: int = Field(10, ge=1, le=500)
    prerequisites_json: Optional[Dict[str, List[int]]] = None


class SkillCreate(SkillBase):
    syllabus_source_file: Optional[str] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    level: Optional[int] = None
    estimated_hours: Optional[int] = None
    prerequisites_json: Optional[Dict[str, List[int]]] = None


class SkillResponse(SkillBase):
    id: int
    syllabus_source_file: Optional[str]
    
    # Динамические поля
    materials_count: int = 0
    challenges_count: int = 0
    completion_rate: float = 0.0  # Процент студентов, которые прошли

    class Config:
        from_attributes = True


class SkillTreeNode(BaseModel):
    """Узел дерева навыков для визуализации"""
    id: int
    name: str
    level: int
    is_global: bool
    status: str  # locked, in_progress, verified
    progress_percentage: int = 0
    children: List['SkillTreeNode'] = []
    position: Optional[Dict[str, float]] = None  # {"x": 0, "y": 0} для React Flow

    class Config:
        from_attributes = True


# ============= MATERIALS (Материалы) =============

class MaterialBase(BaseModel):
    skill_id: int
    type: str  # lecture, video, code_task, 3d_model, article, quiz
    title: str = Field(..., min_length=3, max_length=200)
    content: Dict[str, Any]  # Гибкий JSONB контент


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None


class MaterialResponse(MaterialBase):
    id: int
    author_id: int
    author_type: str
    rating: int
    views: int
    status: str
    created_at: str
    updated_at: str
    
    # Дополнительно
    author_name: Optional[str] = None
    user_has_liked: bool = False

    class Config:
        from_attributes = True


class MaterialVote(BaseModel):
    """Лайк/дизлайк материала"""
    rating: int = Field(..., ge=-1, le=1)  # -1, 0 (убрать), 1
    comment: Optional[str] = None


# ============= CHALLENGES (Челленджи) =============

class ChallengeBase(BaseModel):
    skill_id: int
    title: str = Field(..., min_length=5, max_length=200)
    task_description: str = Field(..., min_length=20)
    requirements: Optional[Dict[str, Any]] = None
    verification_type: str  # ai_vision, manual_employer, auto_test
    ai_validation_prompt: Optional[str] = None
    points: int = Field(100, ge=10, le=1000)
    max_attempts: int = Field(3, ge=1, le=10)
    deadline: Optional[str] = None


class ChallengeCreate(ChallengeBase):
    pass


class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    task_description: Optional[str] = None
    requirements: Optional[Dict[str, Any]] = None
    points: Optional[int] = None
    is_active: Optional[bool] = None


class ChallengeResponse(ChallengeBase):
    id: int
    employer_id: int
    is_active: bool
    created_at: str
    
    # Дополнительно
    employer_name: Optional[str] = None
    submissions_count: int = 0
    completion_rate: float = 0.0

    class Config:
        from_attributes = True


# ============= SUBMISSIONS (Решения) =============

class SubmissionCreate(BaseModel):
    challenge_id: int
    submission_file: str  # URL загруженного файла
    description: Optional[str] = None
    submission_metadata: Optional[Dict[str, Any]] = None


class SubmissionResponse(BaseModel):
    id: int
    challenge_id: int
    user_id: int
    submission_file: str
    description: Optional[str]
    status: str
    ai_check_result: Optional[Dict[str, Any]]
    manual_check_result: Optional[Dict[str, Any]]
    feedback: Optional[str]
    score: Optional[int]
    attempt_number: int
    submitted_at: str
    checked_at: Optional[str]

    class Config:
        from_attributes = True


class SubmissionVerdict(BaseModel):
    """Вердикт по проверке челленджа"""
    status: str  # approved, rejected
    score: int = Field(..., ge=0, le=100)
    feedback: str


# ============= PROGRESS (Прогресс) =============

class ProgressUpdate(BaseModel):
    """Обновление прогресса"""
    status: Optional[str] = None  # locked, in_progress, verified
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    proof_artifact: Optional[str] = None
    proof_metadata: Optional[Dict[str, Any]] = None


class ProgressResponse(BaseModel):
    id: int
    user_id: int
    skill_id: int
    status: str
    progress_percentage: int
    materials_completed: List[int]
    proof_artifact: Optional[str]
    score: Optional[int]
    verified_by: Optional[int]
    verification_comment: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    verified_at: Optional[str]

    class Config:
        from_attributes = True


# ============= SYLLABUS PARSING =============

class SyllabusParseRequest(BaseModel):
    """Запрос на парсинг учебного плана"""
    specialty_name: str
    specialty_code: Optional[str] = None


class SyllabusParseResponse(BaseModel):
    """Результат парсинга"""
    status: str  # success, error
    skills_created: int
    tree_structure: List[Dict[str, Any]]
    warnings: List[str] = []
    errors: List[str] = []


# ============= DASHBOARD =============

class StudentDashboard(BaseModel):
    """Дашборд студента"""
    total_skills: int
    completed_skills: int
    in_progress_skills: int
    locked_skills: int
    completion_percentage: float
    total_points: int
    current_level: int
    challenges_completed: int
    materials_viewed: int
    recent_achievements: List[Dict[str, Any]]


class SkillStatistics(BaseModel):
    """Статистика по навыку"""
    skill_id: int
    skill_name: str
    total_students: int
    completed_students: int
    average_time_hours: float
    average_score: float
    popular_materials: List[Dict[str, Any]]