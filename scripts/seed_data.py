"""
Скрипт для загрузки тестовых данных (5 университетов Алматы)
Запуск: python -m scripts.seed_data
"""
import asyncio
import sys
import os
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal
from app.db.models import (
    University, Program, Faculty, Department,
    Grant, Dormitory, Partnership, User, Admission
)
from app.core.security import get_password_hash


async def create_users(db: AsyncSession):
    """Создать тестовых пользователей"""
    users = [
        User(
            email="admin@university.kz",
            password_hash=get_password_hash("admin123"),
            full_name="Администратор",
            role="admin"
        ),
        User(
            email="student@gmail.com",
            password_hash=get_password_hash("student123"),
            full_name="Айдар Нурланов",
            role="user"
        )
    ]

    for user in users:
        db.add(user)

    print("✅ Созданы пользователи:")
    print("   - admin@university.kz / admin123")
    print("   - student@gmail.com / student123")


async def create_satbayev(db: AsyncSession):
    """Satbayev University - технический флагман"""
    satbayev = University(
        name_ru="Satbayev University",
        name_en="Satbayev University",
        full_name="Казахский национальный исследовательский технический университет имени К.И. Сатпаева",
        type="public",
        status="национальный, исследовательский",
        founded_year=1934,
        city="Алматы",
        address="ул. Сатпаева, 22а",
        latitude=43.2378,
        longitude=76.9453,
        website="https://satbayev.university",
        logo_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/Satbayev_University_logo.svg/800px-Satbayev_University_logo.svg.png",
        virtual_tour_url="https://satbayev.university/virtual-tour",
        description="Ведущий технический университет Казахстана, готовящий инженеров мирового уровня с 1934 года",
        mission="Подготовка высококвалифицированных кадров для развития технологического потенциала страны",
        rating=4.6,
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
        employment_rate=87.0,
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
        dean_name="Омаров Рустам Турсунбаевич",
        phone="+7 (727) 292-11-22"
    )
    db.add(it_faculty)
    await db.flush()

    # Программы
    programs = [
        Program(
            university_id=satbayev.id, faculty_id=it_faculty.id,
            code="6B06101", name_ru="Информационные системы",
            degree="bachelor", price=1200000, duration=4,
            language="ru", min_score=100, study_form="очная"
        ),
        Program(
            university_id=satbayev.id, faculty_id=it_faculty.id,
            code="6B06102", name_ru="Вычислительная техника и ПО",
            degree="bachelor", price=1300000, duration=4,
            language="ru", min_score=105, study_form="очная"
        ),
        Program(
            university_id=satbayev.id, faculty_id=it_faculty.id,
            code="7M06101", name_ru="Информационные системы",
            degree="master", price=1500000, duration=2,
            language="ru", study_form="очная"
        ),
    ]
    for prog in programs:
        db.add(prog)

    # Гранты
    db.add(Grant(
        university_id=satbayev.id,
        name="Государственный грант",
        type="government",
        description="Полное покрытие стоимости обучения для обладателей высоких баллов ЕНТ",
        available_for_applicants=True,
        applicants_count=450,
        min_score_for_grant=120
    ))

    # Общежитие
    db.add(Dormitory(
        university_id=satbayev.id,
        name="Общежитие №1",
        address="ул. Джандосова, 1",
        capacity=800,
        occupied=650,
        rooms_type="2-3 местные",
        price_per_month=20000,
        has_wifi=True,
        has_kitchen=True,
        description="Комфортное общежитие рядом с главным корпусом"
    ))

    # Поступление
    db.add(Admission(
        university_id=satbayev.id,
        degree="bachelor",
        application_start=date(2025, 6, 20),
        application_end=date(2025, 7, 25),
        min_score=100,
        required_documents=["ЕНТ сертификат", "Аттестат", "Удостоверение личности"],
        application_process="Подача документов через портал university.satbayev.kz"
    ))

    print(f"✅ {satbayev.name_ru}")


async def create_kimep(db: AsyncSession):
    """KIMEP University - международный бизнес-вуз"""
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
        logo_url="https://kimep.kz/assets/logo.png",
        description="Первый международный университет в Центральной Азии с преподаванием на английском языке",
        mission="Образование мирового класса в области бизнеса и менеджмента",
        rating=4.4,
        national_ranking=5,
        rector_name="Chan Young Bang",
        total_students=4500,
        international_students=1200,
        total_teachers=350,
        phone="+7 (727) 270-44-44",
        email="info@kimep.kz",
        instagram="@kimepuniversity",
        employment_rate=92.0,
        has_dormitory=True
    )
    db.add(kimep)
    await db.flush()

    programs = [
        Program(
            university_id=kimep.id,
            code="BBA", name_ru="Бизнес администрирование", name_en="Business Administration",
            degree="bachelor", price=2500000, duration=4,
            language="en", min_score=110, study_form="очная"
        ),
        Program(
            university_id=kimep.id,
            code="MBA", name_ru="MBA", name_en="Master of Business Administration",
            degree="master", price=4000000, duration=2,
            language="en", study_form="очная"
        )
    ]
    for prog in programs:
        db.add(prog)

    print(f"✅ {kimep.name_ru}")


async def create_almau(db: AsyncSession):
    """AlmaU - первая бизнес-школа Казахстана"""
    almau = University(
        name_ru="AlmaU",
        name_en="Almaty Management University",
        full_name="Алматы Менеджмент Университет",
        type="private",
        founded_year=1988,
        city="Алматы",
        address="ул. Розыбакиева, 227",
        website="https://almau.edu.kz",
        logo_url="https://almau.edu.kz/logo.png",
        description="Первая бизнес-школа Казахстана, лидер в области бизнес-образования",
        rating=4.3,
        total_students=5000,
        phone="+7 (727) 302-25-25",
        email="info@almau.edu.kz",
        instagram="@almau_official",
        has_dormitory=False,
        employment_rate=88.0
    )
    db.add(almau)
    await db.flush()

    programs = [
        Program(
            university_id=almau.id,
            name_ru="Менеджмент",
            degree="bachelor", price=1800000, duration=4,
            language="ru", min_score=95, study_form="очная"
        ),
        Program(
            university_id=almau.id,
            name_ru="Маркетинг",
            degree="bachelor", price=1800000, duration=4,
            language="ru", min_score=95, study_form="очная"
        )
    ]
    for prog in programs:
        db.add(prog)

    print(f"✅ {almau.name_ru}")


async def create_kaznu(db: AsyncSession):
    """КазНУ им. аль-Фараби - главный классический университет"""
    kaznu = University(
        name_ru="КазНУ им. аль-Фараби",
        name_kz="әл-Фараби атындағы ҚазҰУ",
        name_en="Al-Farabi Kazakh National University",
        full_name="Казахский национальный университет имени аль-Фараби",
        type="public",
        status="национальный",
        founded_year=1934,
        city="Алматы",
        address="пр. аль-Фараби, 71",
        latitude=43.2151,
        longitude=76.9452,
        website="https://www.kaznu.kz",
        logo_url="https://www.kaznu.kz/logo.png",
        virtual_tour_url="https://virtual.kaznu.kz",
        description="Главный классический университет Казахстана, лидер в области фундаментальных наук",
        mission="Развитие науки и образования в Казахстане",
        rating=4.7,
        national_ranking=1,
        rector_name="Буркитбаев Мухамбеткали Мырзакулович",
        total_students=22000,
        international_students=2500,
        total_teachers=2100,
        doctors_count=650,
        phd_count=800,
        campus_area=100.0,
        buildings_count=25,
        phone="+7 (727) 377-33-33",
        email="info@kaznu.kz",
        admission_phone="+7 (727) 377-34-34",
        instagram="@kaznuniversity",
        telegram="@kaznu_official",
        youtube="@KazNUalFarabi",
        employment_rate=85.0,
        has_dormitory=True,
        has_military_department=True
    )
    db.add(kaznu)
    await db.flush()

    # Механико-математический факультет
    mech_math = Faculty(
        university_id=kaznu.id,
        name_ru="Механико-математический факультет",
        dean_name="Калменов Тынысбек Шарипович"
    )
    db.add(mech_math)
    await db.flush()

    programs = [
        Program(
            university_id=kaznu.id, faculty_id=mech_math.id,
            code="6B05301", name_ru="Физика",
            degree="bachelor", price=900000, duration=4,
            language="ru", min_score=90, study_form="очная"
        ),
        Program(
            university_id=kaznu.id, faculty_id=mech_math.id,
            code="6B05401", name_ru="Математика",
            degree="bachelor", price=850000, duration=4,
            language="ru", min_score=95, study_form="очная"
        ),
        Program(
            university_id=kaznu.id,
            name_ru="Международные отношения",
            degree="bachelor", price=1100000, duration=4,
            language="ru", min_score=100, study_form="очная"
        )
    ]
    for prog in programs:
        db.add(prog)

    # Гранты
    db.add(Grant(
        university_id=kaznu.id,
        name="Грант Президента РК",
        type="government",
        available_for_applicants=True,
        applicants_count=800,
        min_score_for_grant=125
    ))

    # Общежития
    db.add(Dormitory(
        university_id=kaznu.id,
        name="Студенческий городок",
        capacity=3000,
        occupied=2800,
        rooms_type="2-4 местные",
        price_per_month=18000,
        has_wifi=True,
        has_kitchen=True,
        has_laundry=True
    ))

    print(f"✅ {kaznu.name_ru}")


async def create_iitu(db: AsyncSession):
    """МУИТ - IT университет"""
    iitu = University(
        name_ru="МУИТ",
        name_en="International Information Technology University",
        full_name="Международный университет информационных технологий",
        type="private",
        founded_year=2009,
        city="Алматы",
        address="ул. Манаса, 34/1",
        website="https://iitu.edu.kz",
        logo_url="https://iitu.edu.kz/logo.png",
        description="Специализированный IT-университет с сильной технической базой",
        mission="Подготовка IT-специалистов мирового уровня",
        rating=4.2,
        national_ranking=8,
        total_students=3500,
        international_students=200,
        total_teachers=180,
        phone="+7 (727) 330-00-00",
        email="info@iitu.edu.kz",
        instagram="@iitu_kz",
        employment_rate=94.0,
        has_dormitory=False
    )
    db.add(iitu)
    await db.flush()

    programs = [
        Program(
            university_id=iitu.id,
            name_ru="Разработка программного обеспечения",
            degree="bachelor", price=1600000, duration=4,
            language="ru", min_score=105, study_form="очная"
        ),
        Program(
            university_id=iitu.id,
            name_ru="Кибербезопасность",
            degree="bachelor", price=1700000, duration=4,
            language="ru", min_score=110, study_form="очная"
        ),
        Program(
            university_id=iitu.id,
            name_ru="Data Science",
            degree="master", price=2000000, duration=2,
            language="en", study_form="очная"
        )
    ]
    for prog in programs:
        db.add(prog)

    db.add(Partnership(
        university_id=iitu.id,
        partner_name="Университет Иннополис",
        partner_country="Россия",
        partner_type="university",
        program_type="double_degree"
    ))

    print(f"✅ {iitu.name_ru}")


async def main():
    """Главная функция"""
    print("🚀 Загрузка тестовых данных...\n")

    async with AsyncSessionLocal() as db:
        try:
            await create_users(db)
            print()

            await create_satbayev(db)
            await create_kimep(db)
            await create_almau(db)
            await create_kaznu(db)
            await create_iitu(db)

            await db.commit()
            print("\n✅ Все данные загружены!")
            print("\n📌 Для входа:")
            print("   Admin: admin@university.kz / admin123")
            print("   Student: student@gmail.com / student123")
            print("\n🌐 API Docs: http://localhost:8000/docs")

        except Exception as e:
            await db.rollback()
            print(f"\n❌ Ошибка: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())