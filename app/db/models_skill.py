"""
Модели для системы Skill Tree с социальными функциями
app/db/models_skill.py
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


class SkillType(str, enum.Enum):
    """Тип навыка"""
    HARD = "hard"  # Специфический для специальности
    SOFT = "soft"  # Глобальный для всех


class SkillStatus(str, enum.Enum):
    """Статус прохождения навыка"""
    LOCKED = "locked"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"


class MaterialType(str, enum.Enum):
    """Тип учебного материала"""
    LECTURE = "lecture"
    VIDEO = "video"
    CODE_TASK = "code_task"
    MODEL_3D = "3d_model"
    ARTICLE = "article"
    QUIZ = "quiz"


class MaterialStatus(str, enum.Enum):
    """Статус материала"""
    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


class VerificationType(str, enum.Enum):
    """Способ проверки челленджа"""
    AI_VISION = "ai_vision"
    MANUAL_EMPLOYER = "manual_employer"
    AUTO_TEST = "auto_test"


# ============= МОДЕЛИ =============

class Skill(Base):
    """Древо навыков"""
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)  # "Python", "Лидерство"
    description = Column(Text, nullable=True)
    
    # Иерархия
    parent_id = Column(Integer, ForeignKey("skills.id"), nullable=True)
    parent = relationship("Skill", remote_side=[id], back_populates="children")
    children = relationship("Skill", back_populates="parent", cascade="all, delete-orphan")
    
    # Тип навыка
    is_global = Column(Boolean, default=False)  # True = Soft Skill
    specialty_id = Column(Integer, ForeignKey("professions.id"), nullable=True)
    
    # История генерации
    syllabus_source_file = Column(String, nullable=True)  # PDF файл источник
    
    # Метаданные
    level = Column(Integer, default=1)  # Уровень сложности 1-5
    estimated_hours = Column(Integer, default=10)  # Примерное время изучения
    prerequisites_json = Column(JSON, nullable=True)  # {"required": [id1, id2], "recommended": [id3]}
    
    # Связи
    specialty = relationship("Profession", foreign_keys=[specialty_id])
    materials = relationship("SkillMaterial", back_populates="skill", cascade="all, delete-orphan")
    challenges = relationship("EmployerChallenge", back_populates="skill", cascade="all, delete-orphan")
    user_progress = relationship("UserSkillProgress", back_populates="skill", cascade="all, delete-orphan")


class SkillMaterial(Base):
    """Контент + Wiki (краудсорсинг)"""
    __tablename__ = "skill_materials"

    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    
    # Автор
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author_type = Column(String, default="student")  # admin, teacher, student
    
    # Контент
    type = Column(Enum(MaterialType), nullable=False)
    title = Column(String, nullable=False)
    
    # JSONB гибкость (главная фишка!)
    content = Column(JSON, nullable=False)
    # Примеры:
    # {"video_url": "youtube.com/...", "start_time": 10, "chapters": [...]}
    # {"code": "print('hello')", "lang": "python", "tests": [...]}
    # {"model_url": "sketchfab.com/...", "format": "glb"}
    
    # Социальные метрики
    rating = Column(Integer, default=0)  # Лайки от студентов
    views = Column(Integer, default=0)
    
    # Модерация
    status = Column(Enum(MaterialStatus), default=MaterialStatus.PENDING_REVIEW)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())
    
    # Связи
    skill = relationship("Skill", back_populates="materials")
    author = relationship("User", foreign_keys=[author_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class EmployerChallenge(Base):
    """Челленджи от работодателей (Real-world Cases)"""
    __tablename__ = "employer_challenges"

    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    employer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Описание задачи
    title = Column(String, nullable=False)
    task_description = Column(Text, nullable=False)
    requirements = Column(JSON, nullable=True)  # {"files": ["pdf", "dwg"], "format": "...", "criteria": [...]}
    
    # Способ проверки
    verification_type = Column(Enum(VerificationType), nullable=False)
    
    # AI промпт для проверки (если ai_vision)
    ai_validation_prompt = Column(Text, nullable=True)
    
    # Награды
    points = Column(Integer, default=100)
    certificate_template = Column(String, nullable=True)
    
    # Метаданные
    is_active = Column(Boolean, default=True)
    deadline = Column(String, nullable=True)
    max_attempts = Column(Integer, default=3)
    
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # Связи
    skill = relationship("Skill", back_populates="challenges")
    employer = relationship("User", foreign_keys=[employer_id])
    submissions = relationship("ChallengeSubmission", back_populates="challenge", cascade="all, delete-orphan")


class UserSkillProgress(Base):
    """Прогресс студента по навыкам"""
    __tablename__ = "user_skill_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    
    # Статус
    status = Column(Enum(SkillStatus), default=SkillStatus.LOCKED)
    
    # Прогресс
    progress_percentage = Column(Integer, default=0)  # 0-100
    materials_completed = Column(JSON, default=list)  # [material_id1, material_id2, ...]
    
    # Артефакты (доказательства)
    proof_artifact = Column(String, nullable=True)  # URL загруженного файла
    proof_metadata = Column(JSON, nullable=True)  # {"filename": "...", "size": ..., "uploaded_at": "..."}
    
    # Оценка
    score = Column(Integer, nullable=True)  # Балл за прохождение
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verification_comment = Column(Text, nullable=True)
    
    # Временные метки
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
    verified_at = Column(String, nullable=True)
    
    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="skill_progress")
    skill = relationship("Skill", back_populates="user_progress")
    verifier = relationship("User", foreign_keys=[verified_by])


class ChallengeSubmission(Base):
    """Отправленные решения челленджей"""
    __tablename__ = "challenge_submissions"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("employer_challenges.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Решение
    submission_file = Column(String, nullable=False)  # URL файла
    submission_metadata = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    
    # Проверка
    status = Column(String, default="pending")  # pending, checking, approved, rejected
    ai_check_result = Column(JSON, nullable=True)  # Результат AI проверки
    manual_check_result = Column(JSON, nullable=True)  # Результат ручной проверки
    
    feedback = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    
    # Метаданные
    attempt_number = Column(Integer, default=1)
    submitted_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    checked_at = Column(String, nullable=True)
    
    # Связи
    challenge = relationship("EmployerChallenge", back_populates="submissions")
    user = relationship("User", foreign_keys=[user_id])


class MaterialRating(Base):
    """Лайки/дизлайки материалов"""
    __tablename__ = "material_ratings"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("skill_materials.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)  # 1 = like, -1 = dislike
    comment = Column(Text, nullable=True)
    
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # Связи
    material = relationship("SkillMaterial")
    user = relationship("User")


