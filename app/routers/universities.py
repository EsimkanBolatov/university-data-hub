from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import University, Program, User
from app.schemas.university import (
    UniversityCreate,
    UniversityResponse,
    UniversityListResponse,
    ProgramCreate,
    ProgramResponse
)
from app.dependencies import get_current_user

router = APIRouter(prefix="/universities", tags=["Universities"])


@router.get("/", response_model=list[UniversityListResponse])
async def get_universities(
        city: str | None = None,
        name: str | None = None,
        limit: int = Query(10, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db)
):
    """Получить список университетов с фильтрацией"""
    query = select(University)

    if city:
        query = query.where(University.city.ilike(f"%{city}%"))

    if name:
        query = query.where(University.name_ru.ilike(f"%{name}%"))

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    universities = result.scalars().all()

    return universities


@router.get("/{university_id}", response_model=UniversityResponse)
async def get_university(
        university_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить детальную информацию о университете"""
    query = select(University).where(University.id == university_id).options(
        selectinload(University.programs)
    )
    result = await db.execute(query)
    university = result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=404, detail="Университет не найден")

    return university


@router.post("/", response_model=UniversityResponse)
async def create_university(
        university_data: UniversityCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Создать новый университет (только для админов)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    new_university = University(**university_data.model_dump())
    db.add(new_university)
    await db.commit()
    await db.refresh(new_university)

    return new_university


@router.post("/{university_id}/programs", response_model=ProgramResponse)
async def add_program_to_university(
        university_id: int,
        program_data: ProgramCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить программу к университету (только для админов)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    # Проверяем существование университета
    query = select(University).where(University.id == university_id)
    result = await db.execute(query)
    university = result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=404, detail="Университет не найден")

    new_program = Program(**program_data.model_dump())
    db.add(new_program)
    await db.commit()
    await db.refresh(new_program)

    return new_program


@router.get("/programs/search", response_model=list[ProgramResponse])
async def search_programs(
        min_price: int | None = None,
        max_price: int | None = None,
        degree: str | None = None,
        city: str | None = None,
        db: AsyncSession = Depends(get_db)
):
    """Поиск программ по фильтрам"""
    query = select(Program).join(University)

    if min_price:
        query = query.where(Program.price >= min_price)

    if max_price:
        query = query.where(Program.price <= max_price)

    if degree:
        query = query.where(Program.degree == degree)

    if city:
        query = query.where(University.city.ilike(f"%{city}%"))

    result = await db.execute(query)
    programs = result.scalars().all()

    return programs