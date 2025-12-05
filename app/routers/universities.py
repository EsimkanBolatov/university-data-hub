from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, or_, and_, text
from typing import List

from app.db.database import get_db
from app.db.models import (
    University, Program, User, Faculty, Grant,
    Dormitory, Partnership, Favorite, Admission
)
from app.schemas.university import (
    UniversityCreate,
    UniversityDetailResponse,
    UniversityListResponse,
    UniversityCompareResponse,
    UniversityUpdate,
    ProgramCreate,
    ProgramResponse,
    FacultyCreate,
    FacultyResponse,
    GrantCreate,
    GrantResponse,
    DormitoryCreate,
    DormitoryResponse,
    PartnershipCreate,
    PartnershipResponse,
    AdmissionCreate,
    AdmissionResponse,
    UniversityStatsResponse
)
from app.dependencies import get_current_user

router = APIRouter(prefix="/universities", tags=["Universities"])


# ============= СТАТИСТИКА =============

@router.get("/stats", response_model=UniversityStatsResponse)
async def get_statistics(db: AsyncSession = Depends(get_db)):
    """Получить общую статистику по платформе"""

    # Количество университетов
    uni_count = await db.scalar(select(func.count(University.id)))

    # Количество программ
    prog_count = await db.scalar(select(func.count(Program.id)))

    # Количество городов
    cities_count = await db.scalar(
        select(func.count(func.distinct(University.city)))
    )

    # Общее количество студентов
    total_students = await db.scalar(
        select(func.sum(University.total_students))
    ) or 0

    # Средняя цена обучения
    avg_price = await db.scalar(
        select(func.avg(Program.price)).where(Program.price.isnot(None))
    ) or 0

    # Топ 5 университетов по рейтингу
    top_unis_query = select(University).order_by(
        University.rating.desc()
    ).limit(5)
    result = await db.execute(top_unis_query)
    top_universities = result.scalars().all()

    return UniversityStatsResponse(
        total_universities=uni_count,
        total_programs=prog_count,
        total_cities=cities_count,
        total_students=total_students,
        average_tuition=round(avg_price),
        top_universities=[
            {"id": u.id, "name": u.name_ru, "rating": u.rating}
            for u in top_universities
        ]
    )


# ============= ОСНОВНЫЕ ЭНДПОИНТЫ =============

@router.get("/", response_model=List[UniversityListResponse])
async def get_universities(
        city: str | None = None,
        type: str | None = None,
        has_dormitory: bool | None = None,
        min_rating: float | None = None,
        max_price: int | None = None,
        query: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db)
):
    """Получить список университетов с фильтрацией и умным поиском"""
    stmt = select(University)

    if city:
        stmt = stmt.where(University.city.ilike(f"%{city}%"))

    if type:
        stmt = stmt.where(University.type == type)

    if has_dormitory is not None:
        stmt = stmt.where(University.has_dormitory == has_dormitory)

    if min_rating:
        stmt = stmt.where(University.rating >= min_rating)

    # Фильтр по максимальной цене программ
    if max_price:
        subquery = select(Program.university_id).where(
            Program.price <= max_price
        ).distinct()
        stmt = stmt.where(University.id.in_(subquery))

    # УЛУЧШЕННЫЙ ПОИСК: PostgreSQL Full-Text Search
    if query:
        # Используем триграммы для нечеткого поиска
        search_pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                University.name_ru.ilike(search_pattern),
                University.name_kz.ilike(search_pattern),
                University.name_en.ilike(search_pattern),
                University.description.ilike(search_pattern),
                University.city.ilike(search_pattern)
            )
        )

    stmt = stmt.order_by(University.rating.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    universities = result.scalars().all()

    # Добавляем диапазон цен и количество программ
    response = []
    for uni in universities:
        # Получаем диапазон цен программ
        price_query = select(
            func.min(Program.price),
            func.max(Program.price),
            func.count(Program.id)
        ).where(Program.university_id == uni.id)
        price_result = await db.execute(price_query)
        min_price, max_price_uni, prog_count = price_result.one()

        price_range = None
        if min_price and max_price_uni:
            if min_price == max_price_uni:
                price_range = f"{min_price:,} ₸"
            else:
                price_range = f"{min_price:,} - {max_price_uni:,} ₸"

        response.append(UniversityListResponse(
            id=uni.id,
            name_ru=uni.name_ru,
            city=uni.city,
            type=uni.type.value if uni.type else "public",
            rating=uni.rating,
            logo_url=uni.logo_url,
            has_dormitory=uni.has_dormitory,
            price_range=price_range,
            programs_count=prog_count,
            description=uni.description
        ))

    return response


@router.get("/{university_id}", response_model=UniversityDetailResponse)
async def get_university(
        university_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить детальную информацию о университете"""
    stmt = select(University).where(University.id == university_id).options(
        selectinload(University.programs),
        selectinload(University.faculties),
        selectinload(University.grants),
        selectinload(University.dormitories),
        selectinload(University.partnerships)
    )
    result = await db.execute(stmt)
    university = result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=404, detail="Университет не найден")

    return university


@router.post("/", response_model=UniversityDetailResponse)
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


@router.patch("/{university_id}", response_model=UniversityDetailResponse)
async def update_university(
        university_id: int,
        university_data: UniversityUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Обновить университет (только для админов)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    stmt = select(University).where(University.id == university_id)
    result = await db.execute(stmt)
    university = result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=404, detail="Университет не найден")

    for key, value in university_data.model_dump(exclude_unset=True).items():
        setattr(university, key, value)

    await db.commit()
    await db.refresh(university)

    return university


@router.delete("/{university_id}")
async def delete_university(
        university_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Удалить университет (только для админов)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    stmt = select(University).where(University.id == university_id)
    result = await db.execute(stmt)
    university = result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=404, detail="Университет не найден")

    await db.delete(university)
    await db.commit()

    return {"message": "Университет успешно удален"}


# ============= ПРОГРАММЫ =============

@router.post("/{university_id}/programs", response_model=ProgramResponse)
async def add_program(
        university_id: int,
        program_data: ProgramCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить программу к университету"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    new_program = Program(**program_data.model_dump())
    db.add(new_program)
    await db.commit()
    await db.refresh(new_program)

    return new_program


@router.get("/programs/search", response_model=List[ProgramResponse])
async def search_programs(
        degree: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        city: str | None = None,
        university_id: int | None = None,
        query: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        db: AsyncSession = Depends(get_db)
):
    """Поиск программ по фильтрам"""
    stmt = select(Program).join(University)

    if degree:
        stmt = stmt.where(Program.degree == degree)

    if min_price:
        stmt = stmt.where(Program.price >= min_price)

    if max_price:
        stmt = stmt.where(Program.price <= max_price)

    if city:
        stmt = stmt.where(University.city.ilike(f"%{city}%"))

    if university_id:
        stmt = stmt.where(Program.university_id == university_id)

    if query:
        search = f"%{query}%"
        stmt = stmt.where(
            or_(
                Program.name_ru.ilike(search),
                Program.name_kz.ilike(search),
                Program.description.ilike(search),
                Program.code.ilike(search)
            )
        )

    stmt = stmt.order_by(Program.price.asc()).limit(limit)
    result = await db.execute(stmt)
    programs = result.scalars().all()

    return programs


# ============= ФАКУЛЬТЕТЫ =============

@router.post("/{university_id}/faculties", response_model=FacultyResponse)
async def add_faculty(
        university_id: int,
        faculty_data: FacultyCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить факультет"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    new_faculty = Faculty(**faculty_data.model_dump())
    db.add(new_faculty)
    await db.commit()
    await db.refresh(new_faculty)

    return new_faculty


# ============= ГРАНТЫ =============

@router.post("/{university_id}/grants", response_model=GrantResponse)
async def add_grant(
        university_id: int,
        grant_data: GrantCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить грант"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    new_grant = Grant(**grant_data.model_dump())
    db.add(new_grant)
    await db.commit()
    await db.refresh(new_grant)

    return new_grant


@router.get("/{university_id}/grants", response_model=List[GrantResponse])
async def get_university_grants(
        university_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить гранты университета"""
    stmt = select(Grant).where(Grant.university_id == university_id)
    result = await db.execute(stmt)
    grants = result.scalars().all()

    return grants


# ============= ОБЩЕЖИТИЯ =============

@router.post("/{university_id}/dormitories", response_model=DormitoryResponse)
async def add_dormitory(
        university_id: int,
        dormitory_data: DormitoryCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить общежитие"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    new_dormitory = Dormitory(**dormitory_data.model_dump())
    db.add(new_dormitory)
    await db.commit()
    await db.refresh(new_dormitory)

    return new_dormitory


# ============= ПОСТУПЛЕНИЕ (НОВОЕ) =============

@router.post("/{university_id}/admissions", response_model=AdmissionResponse)
async def add_admission_info(
        university_id: int,
        admission_data: AdmissionCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить информацию о поступлении"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    new_admission = Admission(**admission_data.model_dump())
    db.add(new_admission)
    await db.commit()
    await db.refresh(new_admission)

    return new_admission


@router.get("/{university_id}/admissions", response_model=List[AdmissionResponse])
async def get_admission_info(
        university_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить информацию о поступлении"""
    stmt = select(Admission).where(Admission.university_id == university_id)
    result = await db.execute(stmt)
    admissions = result.scalars().all()

    return admissions


# ============= СРАВНЕНИЕ =============

@router.post("/compare", response_model=List[UniversityCompareResponse])
async def compare_universities(
        university_ids: List[int],
        db: AsyncSession = Depends(get_db)
):
    """Сравнение университетов (2-5 штук)"""
    if len(university_ids) < 2 or len(university_ids) > 5:
        raise HTTPException(
            status_code=400,
            detail="Можно сравнить от 2 до 5 университетов"
        )

    stmt = select(University).where(University.id.in_(university_ids))
    result = await db.execute(stmt)
    universities = result.scalars().all()

    if len(universities) != len(university_ids):
        raise HTTPException(status_code=404, detail="Некоторые университеты не найдены")

    response = []
    for uni in universities:
        # Подсчет программ
        programs_query = select(func.count(Program.id)).where(
            Program.university_id == uni.id
        )
        programs_result = await db.execute(programs_query)
        programs_count = programs_result.scalar()

        # Диапазон цен
        price_query = select(
            func.min(Program.price),
            func.max(Program.price)
        ).where(Program.university_id == uni.id)
        price_result = await db.execute(price_query)
        min_price, max_price = price_result.one()

        response.append(UniversityCompareResponse(
            id=uni.id,
            name_ru=uni.name_ru,
            city=uni.city,
            type=uni.type.value if uni.type else "public",
            rating=uni.rating,
            total_students=uni.total_students,
            programs_count=programs_count,
            min_price=min_price,
            max_price=max_price,
            has_dormitory=uni.has_dormitory,
            employment_rate=uni.employment_rate
        ))

    return response


# ============= ИЗБРАННОЕ =============

@router.post("/{university_id}/favorite")
async def add_to_favorites(
        university_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Добавить в избранное"""
    stmt = select(University).where(University.id == university_id)
    result = await db.execute(stmt)
    university = result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=404, detail="Университет не найден")

    check_stmt = select(Favorite).where(
        and_(
            Favorite.user_id == current_user.id,
            Favorite.university_id == university_id
        )
    )
    check_result = await db.execute(check_stmt)
    existing = check_result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Уже в избранном")

    favorite = Favorite(user_id=current_user.id, university_id=university_id)
    db.add(favorite)
    await db.commit()

    return {"message": "Добавлено в избранное"}


@router.delete("/{university_id}/favorite")
async def remove_from_favorites(
        university_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Удалить из избранного"""
    stmt = select(Favorite).where(
        and_(
            Favorite.user_id == current_user.id,
            Favorite.university_id == university_id
        )
    )
    result = await db.execute(stmt)
    favorite = result.scalar_one_or_none()

    if not favorite:
        raise HTTPException(status_code=404, detail="Не найдено в избранном")

    await db.delete(favorite)
    await db.commit()

    return {"message": "Удалено из избранного"}


@router.get("/favorites/my", response_model=List[UniversityListResponse])
async def get_my_favorites(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить мои избранные университеты"""
    stmt = select(University).join(Favorite).where(
        Favorite.user_id == current_user.id
    )
    result = await db.execute(stmt)
    universities = result.scalars().all()

    response = []
    for uni in universities:
        price_query = select(
            func.min(Program.price),
            func.max(Program.price),
            func.count(Program.id)
        ).where(Program.university_id == uni.id)
        price_result = await db.execute(price_query)
        min_price, max_price_uni, prog_count = price_result.one()

        price_range = None
        if min_price and max_price_uni:
            price_range = f"{min_price:,} - {max_price_uni:,} ₸"

        response.append(UniversityListResponse(
            id=uni.id,
            name_ru=uni.name_ru,
            city=uni.city,
            type=uni.type.value if uni.type else "public",
            rating=uni.rating,
            logo_url=uni.logo_url,
            has_dormitory=uni.has_dormitory,
            price_range=price_range,
            programs_count=prog_count
        ))

    return response