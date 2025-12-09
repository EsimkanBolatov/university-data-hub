# app/routers/favorites.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.db.database import get_db
from app.dependencies import get_current_user
from app.db.models import User, University, Favorite, Program, Grant

router = APIRouter(prefix="/favorites", tags=["Favorites & Comparison"])


# --- Схемы ---
class FavoriteUniversity(BaseModel):
    id: int
    name: str
    city: str
    rating: float
    logo_url: Optional[str]
    min_price: Optional[int]
    programs_count: int
    added_at: datetime

    class Config:
        from_attributes = True


class ComparisonDetail(BaseModel):
    id: int
    name: str
    city: str
    type: str
    rating: float
    founded_year: Optional[int]
    total_students: Optional[int]
    total_teachers: Optional[int]
    programs_count: int
    min_price: Optional[int]
    max_price: Optional[int]
    avg_price: Optional[int]
    grants_count: int
    has_dormitory: bool
    has_military_department: bool
    employment_rate: Optional[float]
    campus_area: Optional[float]
    website: Optional[str]
    logo_url: Optional[str]


class ComparisonResult(BaseModel):
    universities: List[ComparisonDetail]
    winner_categories: dict
    ai_analysis: Optional[str] = None


# --- Избранное ---

@router.post("/add/{university_id}")
async def add_to_favorites(
        university_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить университет в избранное"""

    # Проверяем существование университета
    uni = await db.get(University, university_id)
    if not uni:
        raise HTTPException(404, "Университет не найден")

    # Проверяем, нет ли уже в избранном
    existing = await db.scalar(
        select(Favorite).where(
            and_(
                Favorite.user_id == current_user.id,
                Favorite.university_id == university_id
            )
        )
    )

    if existing:
        raise HTTPException(400, "Университет уже в избранном")

    # Добавляем
    favorite = Favorite(
        user_id=current_user.id,
        university_id=university_id,
        created_at=datetime.utcnow().date()
    )
    db.add(favorite)
    await db.commit()

    return {
        "message": "Добавлено в избранное",
        "university_id": university_id
    }


@router.delete("/remove/{university_id}")
async def remove_from_favorites(
        university_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Удалить из избранного"""

    favorite = await db.scalar(
        select(Favorite).where(
            and_(
                Favorite.user_id == current_user.id,
                Favorite.university_id == university_id
            )
        )
    )

    if not favorite:
        raise HTTPException(404, "Не найдено в избранном")

    await db.delete(favorite)
    await db.commit()

    return {
        "message": "Удалено из избранного",
        "university_id": university_id
    }


@router.get("/my", response_model=List[FavoriteUniversity])
async def get_my_favorites(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить все избранные университеты"""

    stmt = (
        select(University, Favorite.created_at)
        .join(Favorite, Favorite.university_id == University.id)
        .where(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
    )

    result = await db.execute(stmt)
    favorites = result.all()

    output = []
    for uni, added_at in favorites:
        # Получаем информацию о программах
        price_query = select(
            func.min(Program.price),
            func.count(Program.id)
        ).where(Program.university_id == uni.id)

        price_result = await db.execute(price_query)
        min_price, prog_count = price_result.one()

        output.append(FavoriteUniversity(
            id=uni.id,
            name=uni.name_ru,
            city=uni.city,
            rating=uni.rating or 0,
            logo_url=uni.logo_url,
            min_price=min_price,
            programs_count=prog_count,
            added_at=added_at
        ))

    return output


@router.get("/check/{university_id}")
async def check_is_favorite(
        university_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Проверить, находится ли университет в избранном"""

    exists = await db.scalar(
        select(func.count(Favorite.id)).where(
            and_(
                Favorite.user_id == current_user.id,
                Favorite.university_id == university_id
            )
        )
    )

    return {"is_favorite": exists > 0}


# --- Сравнение ---

@router.post("/compare", response_model=ComparisonResult)
async def compare_universities(
        university_ids: List[int] = Field(..., min_items=2, max_items=5),
        include_ai_analysis: bool = False,
        db: AsyncSession = Depends(get_db)
):
    """
    Сравнить университеты (от 2 до 5)
    Опционально: AI анализ через GPT
    """

    if len(university_ids) < 2:
        raise HTTPException(400, "Необходимо минимум 2 университета")

    if len(university_ids) > 5:
        raise HTTPException(400, "Максимум 5 университетов")

    # Получаем университеты
    stmt = select(University).where(University.id.in_(university_ids))
    result = await db.execute(stmt)
    unis = result.scalars().all()

    if len(unis) != len(university_ids):
        raise HTTPException(404, "Некоторые университеты не найдены")

    # Собираем детальную информацию
    comparison_data = []

    for uni in unis:
        # Программы
        prog_query = select(
            func.count(Program.id),
            func.min(Program.price),
            func.max(Program.price),
            func.avg(Program.price)
        ).where(Program.university_id == uni.id)

        prog_result = await db.execute(prog_query)
        prog_count, min_price, max_price, avg_price = prog_result.one()

        # Гранты
        grants_count = await db.scalar(
            select(func.count(Grant.id)).where(Grant.university_id == uni.id)
        )

        comparison_data.append(ComparisonDetail(
            id=uni.id,
            name=uni.name_ru,
            city=uni.city,
            type=uni.type.value if uni.type else "public",
            rating=uni.rating or 0,
            founded_year=uni.founded_year,
            total_students=uni.total_students,
            total_teachers=uni.total_teachers,
            programs_count=prog_count,
            min_price=min_price,
            max_price=max_price,
            avg_price=int(avg_price) if avg_price else None,
            grants_count=grants_count,
            has_dormitory=uni.has_dormitory or False,
            has_military_department=uni.has_military_department or False,
            employment_rate=uni.employment_rate,
            campus_area=uni.campus_area,
            website=uni.website,
            logo_url=uni.logo_url
        ))

    # Определяем победителей по категориям
    winner_categories = {
        "highest_rating": max(comparison_data, key=lambda x: x.rating).id,
        "most_students": max(comparison_data, key=lambda x: x.total_students or 0).id,
        "most_programs": max(comparison_data, key=lambda x: x.programs_count).id,
        "lowest_price": min(comparison_data, key=lambda x: x.min_price or float('inf')).id,
        "most_grants": max(comparison_data, key=lambda x: x.grants_count).id,
        "best_employment": max(comparison_data, key=lambda x: x.employment_rate or 0).id
    }

    # AI анализ (опционально)
    ai_analysis = None
    if include_ai_analysis:
        from app.services.ai_service import AIService
        analysis_result = await AIService.compare_universities(university_ids, db)
        ai_analysis = analysis_result.get("comparison", "")

    return ComparisonResult(
        universities=comparison_data,
        winner_categories=winner_categories,
        ai_analysis=ai_analysis
    )


@router.post("/compare-favorites")
async def compare_my_favorites(
        include_ai_analysis: bool = False,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Сравнить все университеты из избранного"""

    # Получаем ID избранных университетов
    fav_query = select(Favorite.university_id).where(
        Favorite.user_id == current_user.id
    )
    result = await db.execute(fav_query)
    fav_ids = result.scalars().all()

    if len(fav_ids) < 2:
        raise HTTPException(400, "В избранном должно быть минимум 2 университета")

    if len(fav_ids) > 5:
        raise HTTPException(
            400,
            "Слишком много университетов в избранном. Сравните максимум 5."
        )

    # Используем обычное сравнение
    return await compare_universities(
        university_ids=fav_ids,
        include_ai_analysis=include_ai_analysis,
        db=db
    )