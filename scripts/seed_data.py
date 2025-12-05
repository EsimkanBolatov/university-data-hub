"""
Скрипт для загрузки тестовых данных в базу
Запуск: python -m scripts.seed_data
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal
from app.db.models import (
    University, Program, Faculty, Department,
    Grant, Dormitory, Partnership, User
)
from app.core.security import get_password_hash


async def create_admin_user(db: AsyncSession):
    """Создать админа"""
    admin = User(
        email="admin@university.kz",
        password_hash=get_password_hash("admin123"),
        full_name="Администратор",
        role="admin"
    )
    db.add(admin)
    print("✅ Создан админ: admin@university.kz / admin123")


async def create_satbayev_university(db: AsyncSession):
    """Создать Satbayev University с программами"""

    satbayev = University(
        name_ru="Satbayev University",
        name_kz="Satbayev University",
        name_en="Satbayev University",
        full_name="Казахский национальный исследовательский технический университет имени К.И. Сатпаева",
        type="public",
        status="национальный, исследовательский",
        founded_year=1934,
        city="Алматы",
        country="Казахстан",
        address="ул. Сатпаева, 22а",
        latitude=43.2378,
        longitude=76.9453,
        website="https://satbayev.university",
        logo_url="https://satbayev.university/logo.png",
        description="Ведущий технический университет Казахстана с богатой историей и традициями",
        mission="Подготовка высококвалифицированных инженерных кадров",
        rating=4.5,
        national_ranking=3,
        rector_name="Искаков Мади Кенжебекович",
        total_students=16000,
        international_students=800,
        total_teachers=1200,
        doctors_count=300,
        phd_count=450,
        campus_area=45.0,
        buildings_count=15,
        phone="+7 (727) 292-64-84",
        email="info@satbayev.university",
        admission_phone="+7 (727) 292-57-22",
        instagram="@satbayev_university",
        telegram="@satbayevuniversity",
        employment_rate=85.0,
        has_dormitory=True,
        has_military_department=True
    )
    db.add(satbayev)
    await db.flush()

    # Факультет IT
    it_faculty = Faculty(
        university_id=satbayev.id,
        name_ru="Институт информационных и телекоммуникационных технологий",
        name_en="Institute of Information and Telecommunication Technologies",
        description="Подготовка IT-специалистов мирового уровня",
        dean_name="Омаров Рустам Турсунбаевич",
        phone="+7 (727) 292-11-22"
    )
    db.add(it_faculty)
    await db.flush()

    # Программы
    programs_data = [
        {
            "code": "6B06101",
            "name_ru": "Информационные системы",
            "degree": "bachelor",
            "price": 1200000,
            "duration": 4,
            "language": "ru",
            "min_score": 100,
            "study_form": "очная",
            "faculty_id": it_faculty.id
        },
        {
            "code": "6B06102",
            "name_ru": "Вычислительная техника и программное обеспечение",
            "degree": "bachelor",
            "price": 1300000,
            "duration": 4,
            "language": "ru",
            "min_score": 105,
            "study_form": "очная",
            "faculty_id": it_faculty.id
        },
        {
            "code": "7M06101",
            "name_ru": "Информационные системы",
            "degree": "master",
            "price": 1500000,
            "duration": 2,
            "language": "ru",
            "min_score": 0,
            "study_form": "очная",
            "faculty_id": it_faculty.id
        }
    ]

    for prog_data in programs_data:
        program = Program(university_id=satbayev.id, **prog_data)
        db.add(program)

    # Гранты
    grant1 = Grant(
        university_id=satbayev.id,
        name="Государственный грант",
        type="government",
        description="Полное покрытие стоимости обучения",
        available_for_applicants=True,
        applicants_count=450,
        min_score_for_grant=120
    )
    db.add(grant1)

    # Общежитие
    dorm1 = Dormitory(
        university_id=satbayev.id,
        name="Общежитие №1",
        address="ул. Джандосова, 1",
        capacity=800,
        occupied=650,
        rooms_type="2-3 местные",
        price_per_month=20000,
        has_wifi=True,
        has_kitchen=True,
        has_laundry=True,
        description="Комфортное общежитие рядом с главным корпусом"
    )
    db.add(dorm1)

    # Партнерство
    partner1 = Partnership(
        university_id=satbayev.id,
        partner_name="Technical University of Berlin",
        partner_country="Германия",
        partner_type="university",
        program_type="exchange",
        description="Программа академического обмена студентами"
    )
    db.add(partner1)

    print(f"✅ Создан университет: {satbayev.name_ru}")


async def create_kimep_university(db: AsyncSession):
    """Создать KIMEP University"""

    kimep = University(
        name_ru="KIMEP University",
        name_en="KIMEP University",
        full_name="Казахстанский институт менеджмента, экономики и стратегических исследований",
        type="private",
        status="международный",
        founded_year=1992,
        city="Алматы",
        address="ул. Абая, 4",
        latitude=43.2391,
        longitude=76.9144,
        website="https://kimep.kz",
        description="Первый международный университет в Центральной Азии",
        mission="Образование мирового класса на английском языке",
        rating=4.3,
        national_ranking=5,
        rector_name="Chan Young Bang",
        total_students=4500,
        international_students=1200,
        total_teachers=350,
        phone="+7 (727) 270-44-44",
        email="info@kimep.kz",
        instagram="@kimepuniversity",
        employment_rate=90.0,
        has_dormitory=True
    )
    db.add(kimep)
    await db.flush()

    # Программы
    programs = [
        Program(
            university_id=kimep.id,
            code="BBA",
            name_ru="Бизнес администрирование",
            name_en="Business Administration",
            degree="bachelor",
            price=2500000,
            duration=4,
            language="en",
            min_score=110,
            study_form="очная"
        ),
        Program(
            university_id=kimep.id,
            code="MBA",
            name_ru="MBA",
            name_en="Master of Business Administration",
            degree="master",
            price=4000000,
            duration=2,
            language="en",
            study_form="очная"
        )
    ]

    for prog in programs:
        db.add(prog)

    print(f"✅ Создан университет: {kimep.name_ru}")


async def create_alu_university(db: AsyncSession):
    """Создать ALU (Almaty Management University)"""

    alu = University(
        name_ru="AlmaU",
        name_en="Almaty Management University",
        full_name="Алматы Менеджмент Университет",
        type="private",
        founded_year=1988,
        city="Алматы",
        address="ул. Розыбакиева, 227",
        website="https://almau.edu.kz",
        description="Первая бизнес-школа Казахстана",
        rating=4.2,
        total_students=5000,
        phone="+7 (727) 302-25-25",
        email="info@almau.edu.kz",
        has_dormitory=False,
        employment_rate=88.0
    )
    db.add(alu)
    await db.flush()

    programs = [
        Program(
            university_id=alu.id,
            name_ru="Менеджмент",
            degree="bachelor",
            price=1800000,
            duration=4,
            language="ru",
            min_score=95
        ),
        Program(
            university_id=alu.id,
            name_ru="Маркетинг",
            degree="bachelor",
            price=1800000,
            duration=4,
            language="ru",
            min_score=95
        )
    ]

    for prog in programs:
        db.add(prog)

    print(f"✅ Создан университет: {alu.name_ru}")


async def main():
    """Главная функция"""
    print("🚀 Начинаем загрузку тестовых данных...\n")

    async with AsyncSessionLocal() as db:
        try:
            await create_admin_user(db)
            await create_satbayev_university(db)
            await create_kimep_university(db)
            await create_alu_university(db)

            await db.commit()
            print("\n✅ Все данные успешно загружены!")
            print("\n📌 Для входа используй:")
            print("   Email: admin@university.kz")
            print("   Password: admin123")

        except Exception as e:
            await db.rollback()
            print(f"\n❌ Ошибка: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())