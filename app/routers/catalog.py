# app/routers/catalog.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import List, Optional
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.db.models import University, Program, Grant, Favorite
from app.dependencies import get_current_user
from app.db.models import User

router = APIRouter(prefix="/catalog", tags=["Catalog"])


# --- Схемы ---
class UniversityCard(BaseModel):
    id: int
    name: str
    city: str
    type: str
    rating: float
    logo_url: Optional[str]
    min_price: Optional[int]
    max_price: Optional[int]
    programs_count: int
    students_count: Optional[int]
    has_dormitory: bool
    employment_rate: Optional[float]
    is_favorite: bool = False

    class Config:
        from_attributes = True


class CatalogFilters(BaseModel):
    query: Optional[str] = Field(None, description="Поисковый запрос")
    city: Optional[str] = Field(None, description="Город")
    type: Optional[str] = Field(None, description="Тип: public/private/international")
    min_rating: Optional[float] = Field(None, ge=0, le=10)
    max_rating: Optional[float] = Field(None, ge=0, le=10)
    min_price: Optional[int] = Field(None, ge=0)
    max_price: Optional[int] = Field(None, ge=0)
    has_dormitory: Optional[bool] = None
    has_grants: Optional[bool] = None
    min_students: Optional[int] = Field(None, ge=0)
    degree: Optional[str] = Field(None, description="bachelor/master/phd")
    sort_by: str = Field("rating", description="rating/price/students/name")
    sort_order: str = Field("desc", description="asc/desc")
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class CatalogResponse(BaseModel):
    universities: List[UniversityCard]
    total: int
    page: int
    per_page: int
    total_pages: int
    filters_applied: dict


# --- Эндпоинты ---

@router.get("/universities", response_model=CatalogResponse)
async def get_catalog(
        query: Optional[str] = None,
        city: Optional[str] = None,
        type: Optional[str] = None,
        min_rating: Optional[float] = Query(None, ge=0, le=10),
        max_rating: Optional[float] = Query(None, ge=0, le=10),
        min_price: Optional[int] = Query(None, ge=0),
        max_price: Optional[int] = Query(None, ge=0),
        has_dormitory: Optional[bool] = None,
        has_grants: Optional[bool] = None,
        min_students: Optional[int] = Query(None, ge=0),
        degree: Optional[str] = None,
        sort_by: str = Query("rating", regex="^(rating|price|students|name)$"),
        sort_order: str = Query("desc", regex="^(asc|desc)$"),
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user)
):
    """
    Каталог университетов с расширенными фильтрами
    """

    # Базовый запрос
    stmt = select(University)
    count_stmt = select(func.count(University.id))

    # Применяем фильтры
    conditions = []

    if query:
        search_pattern = f"%{query}%"
        conditions.append(or_(
            University.name_ru.ilike(search_pattern),
            University.name_kz.ilike(search_pattern),
            University.name_en.ilike(search_pattern),
            University.description.ilike(search_pattern)
        ))

    if city:
        conditions.append(University.city.ilike(f"%{city}%"))

    if type:
        conditions.append(University.type == type)

    if min_rating is not None:
        conditions.append(University.rating >= min_rating)

    if max_rating is not None:
        conditions.append(University.rating <= max_rating)

    if has_dormitory is not None:
        conditions.append(University.has_dormitory == has_dormitory)

    if min_students is not None:
        conditions.append(University.total_students >= min_students)

    # Фильтр по цене программ
    if min_price is not None or max_price is not None:
        price_subquery = select(Program.university_id).distinct()
        if min_price is not None:
            price_subquery = price_subquery.where(Program.price >= min_price)
        if max_price is not None:
            price_subquery = price_subquery.where(Program.price <= max_price)
        conditions.append(University.id.in_(price_subquery))

    # Фильтр по степени программ
    if degree:
        degree_subquery = select(Program.university_id).where(
            Program.degree == degree
        ).distinct()
        conditions.append(University.id.in_(degree_subquery))

    # Фильтр по наличию грантов
    if has_grants:
        grants_subquery = select(Grant.university_id).distinct()
        conditions.append(University.id.in_(grants_subquery))

    # Применяем все условия
    if conditions:
        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))

    # Подсчёт общего количества
    total = await db.scalar(count_stmt)

    # Сортировка
    if sort_by == "rating":
        order_col = University.rating
    elif sort_by == "students":
        order_col = University.total_students
    elif sort_by == "name":
        order_col = University.name_ru
    else:
        order_col = University.rating

    if sort_order == "desc":
        stmt = stmt.order_by(order_col.desc())
    else:
        stmt = stmt.order_by(order_col.asc())

    # Пагинация
    offset = (page - 1) * per_page
    stmt = stmt.limit(per_page).offset(offset)

    # Выполнение запроса
    result = await db.execute(stmt)
    universities = result.scalars().all()

    # Получаем избранное текущего пользователя
    favorite_ids = set()
    if current_user:
        fav_query = select(Favorite.university_id).where(
            Favorite.user_id == current_user.id
        )
        fav_result = await db.execute(fav_query)
        favorite_ids = set(fav_result.scalars().all())

    # Формируем карточки
    cards = []
    for uni in universities:
        # Цены программ
        price_query = select(
            func.min(Program.price),
            func.max(Program.price),
            func.count(Program.id)
        ).where(Program.university_id == uni.id)

        price_result = await db.execute(price_query)
        min_p, max_p, prog_count = price_result.one()

        cards.append(UniversityCard(
            id=uni.id,
            name=uni.name_ru,
            city=uni.city,
            type=uni.type.value if uni.type else "public",
            rating=uni.rating or 0,
            logo_url=uni.logo_url,
            min_price=min_p,
            max_price=max_p,
            programs_count=prog_count,
            students_count=uni.total_students,
            has_dormitory=uni.has_dormitory or False,
            employment_rate=uni.employment_rate,
            is_favorite=(uni.id in favorite_ids)
        ))

    total_pages = (total + per_page - 1) // per_page

    return CatalogResponse(
        universities=cards,
        total=total or 0,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        filters_applied={
            "query": query,
            "city": city,
            "type": type,
            "min_rating": min_rating,
            "max_rating": max_rating,
            "min_price": min_price,
            "max_price": max_price,
            "has_dormitory": has_dormitory,
            "has_grants": has_grants,
            "degree": degree
        }
    )


@router.get("/cities")
async def get_available_cities(db: AsyncSession = Depends(get_db)):
    """Получить список доступных городов"""
    result = await db.execute(
        select(University.city, func.count(University.id).label('count'))
        .group_by(University.city)
        .order_by(func.count(University.id).desc())
    )
    cities = [{"name": row[0], "count": row[1]} for row in result.all()]
    return {"cities": cities}


@router.get("/stats")
async def get_catalog_stats(db: AsyncSession = Depends(get_db)):
    """Статистика каталога"""

    total_unis = await db.scalar(select(func.count(University.id)))
    total_progs = await db.scalar(select(func.count(Program.id)))

    avg_rating = await db.scalar(select(func.avg(University.rating)))

    avg_price = await db.scalar(
        select(func.avg(Program.price)).where(Program.price.isnot(None))
    )

    cities_count = await db.scalar(
        select(func.count(func.distinct(University.city)))
    )

    return {
        "total_universities": total_unis or 0,
        "total_programs": total_progs or 0,
        "average_rating": round(avg_rating or 0, 2),
        "average_price": int(avg_price or 0),
        "cities_count": cities_count or 0
    }