"""
API эндпоинты для Skill Tree системы
app/routers/skill_tree.py
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
import tempfile
from pathlib import Path

from app.db.database import get_db
from app.dependencies import get_current_user
from app.db.models import User, Skill, SkillMaterial, EmployerChallenge, UserSkillProgress, ChallengeSubmission, MaterialRating
from app.schemas.skill import *
from app.services.syllabus_parser_service import SyllabusParserService
from app.services.challenge_validator_service import ChallengeValidatorService

router = APIRouter(prefix="/skills", tags=["Skill Tree"])


# ============= НАВЫКИ (SKILLS) =============

@router.post("/", response_model=SkillResponse)
async def create_skill(
    skill: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать навык (админ/преподаватель)"""
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(403, "Недостаточно прав")
    
    new_skill = Skill(**skill.model_dump())
    db.add(new_skill)
    await db.commit()
    await db.refresh(new_skill)
    
    # Добавляем динамические поля
    response = SkillResponse.model_validate(new_skill)
    response.materials_count = 0
    response.challenges_count = 0
    response.completion_rate = 0.0
    
    return response


@router.get("/tree", response_model=List[SkillTreeNode])
async def get_skill_tree(
    specialty_id: Optional[int] = None,
    include_global: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить дерево навыков для специальности
    
    - specialty_id: ID специальности (если None, показывает все)
    - include_global: включать ли Soft Skills
    """
    
    # Базовый запрос
    stmt = select(Skill).where(Skill.parent_id.is_(None))  # Корневые узлы
    
    if specialty_id:
        if include_global:
            stmt = stmt.where(
                or_(
                    Skill.specialty_id == specialty_id,
                    Skill.is_global == True
                )
            )
        else:
            stmt = stmt.where(Skill.specialty_id == specialty_id)
    elif not include_global:
        stmt = stmt.where(Skill.is_global == False)
    
    stmt = stmt.options(selectinload(Skill.children))
    
    result = await db.execute(stmt)
    root_skills = result.scalars().all()
    
    # Получаем прогресс пользователя
    progress_map = await _get_user_progress_map(current_user.id, db)
    
    # Строим дерево
    tree = []
    for skill in root_skills:
        node = await _build_tree_node(skill, progress_map, db)
        tree.append(node)
    
    return tree


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить детальную информацию о навыке"""
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Навык не найден")
    
    # Считаем метрики
    materials_count = await db.scalar(
        select(func.count(SkillMaterial.id)).where(
            SkillMaterial.skill_id == skill_id
        )
    )
    
    challenges_count = await db.scalar(
        select(func.count(EmployerChallenge.id)).where(
            EmployerChallenge.skill_id == skill_id
        )
    )
    
    # Процент завершивших
    total_users = await db.scalar(
        select(func.count(UserSkillProgress.id)).where(
            UserSkillProgress.skill_id == skill_id
        )
    )
    
    completed_users = await db.scalar(
        select(func.count(UserSkillProgress.id)).where(
            and_(
                UserSkillProgress.skill_id == skill_id,
                UserSkillProgress.status == "verified"
            )
        )
    )
    
    completion_rate = (completed_users / total_users * 100) if total_users > 0 else 0
    
    response = SkillResponse.model_validate(skill)
    response.materials_count = materials_count or 0
    response.challenges_count = challenges_count or 0
    response.completion_rate = round(completion_rate, 2)
    
    return response


@router.patch("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: int,
    skill_update: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить навык"""
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(403, "Недостаточно прав")
    
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Навык не найден")
    
    for key, value in skill_update.model_dump(exclude_unset=True).items():
        setattr(skill, key, value)
    
    await db.commit()
    await db.refresh(skill)
    
    return SkillResponse.model_validate(skill)


# ============= МАТЕРИАЛЫ (MATERIALS) =============

@router.get("/{skill_id}/materials", response_model=List[MaterialResponse])
async def get_skill_materials(
    skill_id: int,
    status: Optional[str] = Query(None, regex="^(approved|pending_review|rejected)$"),
    sort_by: str = Query("rating", regex="^(rating|views|created_at)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить материалы навыка
    
    - Официальные (от админов/преподавателей) всегда сверху
    - Студенческие (wiki) отсортированы по рейтингу
    """
    
    stmt = select(SkillMaterial).where(SkillMaterial.skill_id == skill_id)
    
    if status:
        stmt = stmt.where(SkillMaterial.status == status)
    else:
        # Показываем только одобренные, кроме админов
        if current_user.role not in ["admin", "teacher"]:
            stmt = stmt.where(SkillMaterial.status == "approved")
    
    # Сортировка
    if sort_by == "rating":
        stmt = stmt.order_by(SkillMaterial.rating.desc())
    elif sort_by == "views":
        stmt = stmt.order_by(SkillMaterial.views.desc())
    else:
        stmt = stmt.order_by(SkillMaterial.created_at.desc())
    
    result = await db.execute(stmt)
    materials = result.scalars().all()
    
    # Получаем лайки пользователя
    user_likes = await db.execute(
        select(MaterialRating.material_id).where(
            and_(
                MaterialRating.user_id == current_user.id,
                MaterialRating.rating == 1
            )
        )
    )
    liked_ids = set(user_likes.scalars().all())
    
    # Формируем ответ
    response = []
    for m in materials:
        item = MaterialResponse.model_validate(m)
        item.author_name = (await db.get(User, m.author_id)).full_name
        item.user_has_liked = m.id in liked_ids
        response.append(item)
    
    return response


@router.post("/{skill_id}/materials", response_model=MaterialResponse)
async def create_material(
    skill_id: int,
    material: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Добавить материал (Краудсорсинг!)
    
    - Админ/преподаватель: сразу approved
    - Студент: pending_review
    """
    
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Навык не найден")
    
    # Определяем статус
    if current_user.role in ["admin", "teacher"]:
        status = MaterialStatus.APPROVED
        author_type = current_user.role
    else:
        status = MaterialStatus.PENDING_REVIEW
        author_type = "student"
    
    new_material = SkillMaterial(
        skill_id=skill_id,
        author_id=current_user.id,
        author_type=author_type,
        type=material.type,
        title=material.title,
        content=material.content,
        status=status
    )
    
    db.add(new_material)
    await db.commit()
    await db.refresh(new_material)
    
    response = MaterialResponse.model_validate(new_material)
    response.author_name = current_user.full_name
    
    return response


@router.post("/materials/{material_id}/vote")
async def vote_material(
    material_id: int,
    vote: MaterialVote,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Лайк/дизлайк материала"""
    
    material = await db.get(SkillMaterial, material_id)
    if not material:
        raise HTTPException(404, "Материал не найден")
    
    # Ищем существующий рейтинг
    existing = await db.scalar(
        select(MaterialRating).where(
            and_(
                MaterialRating.material_id == material_id,
                MaterialRating.user_id == current_user.id
            )
        )
    )
    
    if vote.rating == 0:  # Убрать голос
        if existing:
            material.rating -= existing.rating
            await db.delete(existing)
    else:
        if existing:
            # Обновить
            old_rating = existing.rating
            existing.rating = vote.rating
            existing.comment = vote.comment
            material.rating += (vote.rating - old_rating)
        else:
            # Создать новый
            new_rating = MaterialRating(
                material_id=material_id,
                user_id=current_user.id,
                rating=vote.rating,
                comment=vote.comment
            )
            db.add(new_rating)
            material.rating += vote.rating
    
    await db.commit()
    
    return {"rating": material.rating, "message": "Голос учтён"}


# ============= ЧЕЛЛЕНДЖИ (CHALLENGES) =============

@router.get("/{skill_id}/challenges", response_model=List[ChallengeResponse])
async def get_skill_challenges(
    skill_id: int,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Получить челленджи для навыка"""
    
    stmt = select(EmployerChallenge).where(
        EmployerChallenge.skill_id == skill_id
    )
    
    if active_only:
        stmt = stmt.where(EmployerChallenge.is_active == True)
    
    result = await db.execute(stmt)
    challenges = result.scalars().all()
    
    # Добавляем метрики
    response = []
    for c in challenges:
        item = ChallengeResponse.model_validate(c)
        
        employer = await db.get(User, c.employer_id)
        item.employer_name = employer.full_name if employer else "Unknown"
        
        item.submissions_count = await db.scalar(
            select(func.count(ChallengeSubmission.id)).where(
                ChallengeSubmission.challenge_id == c.id
            )
        )
        
        response.append(item)
    
    return response


@router.post("/challenges", response_model=ChallengeResponse)
async def create_challenge(
    challenge: ChallengeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать челлендж (работодатель)"""
    
    # Проверяем навык
    skill = await db.get(Skill, challenge.skill_id)
    if not skill:
        raise HTTPException(404, "Навык не найден")
    
    new_challenge = EmployerChallenge(
        **challenge.model_dump(),
        employer_id=current_user.id
    )
    
    db.add(new_challenge)
    await db.commit()
    await db.refresh(new_challenge)
    
    response = ChallengeResponse.model_validate(new_challenge)
    response.employer_name = current_user.full_name
    response.submissions_count = 0
    
    return response


@router.post("/challenges/{challenge_id}/submit", response_model=SubmissionResponse)
async def submit_challenge(
    challenge_id: int,
    submission: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отправить решение челленджа"""
    
    challenge = await db.get(EmployerChallenge, challenge_id)
    if not challenge:
        raise HTTPException(404, "Челлендж не найден")
    
    if not challenge.is_active:
        raise HTTPException(400, "Челлендж неактивен")
    
    # Проверяем количество попыток
    attempts = await db.scalar(
        select(func.count(ChallengeSubmission.id)).where(
            and_(
                ChallengeSubmission.challenge_id == challenge_id,
                ChallengeSubmission.user_id == current_user.id
            )
        )
    )
    
    if attempts >= challenge.max_attempts:
        raise HTTPException(400, f"Превышен лимит попыток ({challenge.max_attempts})")
    
    # Создаём submission
    new_submission = ChallengeSubmission(
        challenge_id=challenge_id,
        user_id=current_user.id,
        submission_file=submission.submission_file,
        description=submission.description,
        submission_metadata=submission.submission_metadata,
        attempt_number=attempts + 1,
        status="pending"
    )
    
    db.add(new_submission)
    await db.commit()
    await db.refresh(new_submission)
    
    # Запускаем валидацию в фоне
    validation_result = await ChallengeValidatorService.validate_submission(
        new_submission.id,
        db
    )
    
    await db.refresh(new_submission)
    
    return SubmissionResponse.model_validate(new_submission)


# ============= ПРОГРЕСС (PROGRESS) =============

@router.get("/my-progress", response_model=StudentDashboard)
async def get_my_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Дашборд прогресса студента"""
    
    # Все навыки студента
    total_skills = await db.scalar(
        select(func.count(UserSkillProgress.id)).where(
            UserSkillProgress.user_id == current_user.id
        )
    )
    
    completed = await db.scalar(
        select(func.count(UserSkillProgress.id)).where(
            and_(
                UserSkillProgress.user_id == current_user.id,
                UserSkillProgress.status == "verified"
            )
        )
    )
    
    in_progress = await db.scalar(
        select(func.count(UserSkillProgress.id)).where(
            and_(
                UserSkillProgress.user_id == current_user.id,
                UserSkillProgress.status == "in_progress"
            )
        )
    )
    
    locked = total_skills - completed - in_progress
    
    # Баллы
    total_points = await db.scalar(
        select(func.sum(UserSkillProgress.score)).where(
            UserSkillProgress.user_id == current_user.id
        )
    ) or 0
    
    # Уровень (примерная формула)
    current_level = int(total_points / 1000) + 1
    
    completion = (completed / total_skills * 100) if total_skills > 0 else 0
    
    return StudentDashboard(
        total_skills=total_skills or 0,
        completed_skills=completed or 0,
        in_progress_skills=in_progress or 0,
        locked_skills=locked or 0,
        completion_percentage=round(completion, 2),
        total_points=total_points,
        current_level=current_level,
        challenges_completed=0,  # TODO
        materials_viewed=0,  # TODO
        recent_achievements=[]  # TODO
    )


# ============= ADMIN =============

@router.post("/parse-syllabus", response_model=SyllabusParseResponse)
async def parse_syllabus_pdf(
    specialty_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Парсинг PDF учебного плана в дерево навыков (AI)
    Только для админов
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Только для администраторов")
    
    # Сохраняем временно
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        result = await SyllabusParserService.parse_pdf_to_tree(
            tmp_path,
            specialty_id,
            db
        )
        return result
    finally:
        Path(tmp_path).unlink()


@router.post("/generate-soft-skills")
async def generate_soft_skills(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Генерация глобальных Soft Skills"""
    if current_user.role != "admin":
        raise HTTPException(403, "Только для администраторов")
    
    count = await SyllabusParserService.generate_soft_skills(db)
    
    return {"message": f"Создано {count} Soft Skills"}


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def _get_user_progress_map(user_id: int, db: AsyncSession) -> dict:
    """Карта прогресса пользователя {skill_id: progress}"""
    result = await db.execute(
        select(UserSkillProgress).where(
            UserSkillProgress.user_id == user_id
        )
    )
    progress_list = result.scalars().all()
    
    return {p.skill_id: p for p in progress_list}


async def _build_tree_node(
    skill: Skill,
    progress_map: dict,
    db: AsyncSession
) -> SkillTreeNode:
    """Рекурсивное построение узла дерева"""
    
    progress = progress_map.get(skill.id)
    
    node = SkillTreeNode(
        id=skill.id,
        name=skill.name,
        level=skill.level,
        is_global=skill.is_global,
        status=progress.status if progress else "locked",
        progress_percentage=progress.progress_percentage if progress else 0,
        children=[]
    )
    
    # Рекурсия для детей
    if skill.children:
        for child in skill.children:
            child_node = await _build_tree_node(child, progress_map, db)
            node.children.append(child_node)
    
    return node