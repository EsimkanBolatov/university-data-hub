import enum
from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, Float, ForeignKey, Enum, Text, Boolean, Date, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base
# УДАЛЕНО: from app.db.models import User (Это вызывало ошибку ImportError: circular import)

# ============ АССОЦИАЦИИ ============

university_professions = Table(
    'university_professions', Base.metadata,
    Column('university_id', Integer, ForeignKey('universities.id'), primary_key=True),
    Column('profession_id', Integer, ForeignKey('professions.id'), primary_key=True)
)

# ============ ENUMS ============

class RoleEnum(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class UniversityType(str, enum.Enum):
    PUBLIC = "public"  # Государственный
    PRIVATE = "private"  # Частный
    INTERNATIONAL = "international"  # Международный


class DegreeType(str, enum.Enum):
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"


# ============ МОДЕЛИ ПОЛЬЗОВАТЕЛЕЙ ============

class User(Base):
    """Пользователи системы"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.USER)

    # Связь с избранным
    favorites = relationship("Favorite", back_populates="user")
    
    # ИСПРАВЛЕНО: Убрана лишняя строка User.skill_progress = ...
    # КОММЕНТАРИЙ: relationship закомментирован, так как таблицы UserSkillProgress нет в этом файле. 
    # Раскомментируйте, когда добавите таблицу UserSkillProgress.
    # skill_progress = relationship("UserSkillProgress", back_populates="user")
    
    # Связи для карьерного теста
    career_sessions = relationship("CareerTestSession", back_populates="user")


# ============ УНИВЕРСИТЕТЫ И ОБРАЗОВАНИЕ ============

class University(Base):
    """Университеты"""
    __tablename__ = "universities"

    id = Column(Integer, primary_key=True, index=True)

    # Основная информация
    name_ru = Column(String, nullable=False, index=True)
    name_kz = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    full_name = Column(Text, nullable=True)

    type = Column(Enum(UniversityType), default=UniversityType.PUBLIC)
    status = Column(String, nullable=True)  # национальный, исследовательский, автономный
    founded_year = Column(Integer, nullable=True)

    # Местоположение
    city = Column(String, nullable=False, index=True)
    country = Column(String, default="Казахстан")
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Веб-ресурсы
    website = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    virtual_tour_url = Column(String, nullable=True)

    # Описание
    description = Column(Text, nullable=True)
    # ИСПРАВЛЕНО: mission был объявлен дважды. Убрал дубликат снизу.
    mission = Column(Text, nullable=True)
    values = Column(Text, nullable=True)
    history = Column(Text, nullable=True)

    # Рейтинги
    rating = Column(Float, default=0.0)
    national_ranking = Column(Integer, nullable=True)
    international_ranking = Column(Integer, nullable=True)

    # Руководство
    rector_name = Column(String, nullable=True)
    rector_contacts = Column(String, nullable=True)

    # Статистика
    total_students = Column(Integer, nullable=True)
    international_students = Column(Integer, nullable=True)
    total_teachers = Column(Integer, nullable=True)
    doctors_count = Column(Integer, nullable=True)
    phd_count = Column(Integer, nullable=True)

    # Кампус
    campus_area = Column(Float, nullable=True)  # Площадь в га
    buildings_count = Column(Integer, nullable=True)

    # Лицензии и аккредитации
    license_number = Column(String, nullable=True)
    license_date = Column(Date, nullable=True)
    accreditations = Column(JSON, nullable=True)  # Список аккредитаций

    # Контакты
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    hotline = Column(String, nullable=True)
    admission_phone = Column(String, nullable=True)

    # Социальные сети
    telegram = Column(String, nullable=True)
    instagram = Column(String, nullable=True)
    youtube = Column(String, nullable=True)
    facebook = Column(String, nullable=True)

    # Дополнительная информация
    employment_rate = Column(Float, nullable=True)  # Процент трудоустройства
    has_dormitory = Column(Boolean, default=False)
    has_military_department = Column(Boolean, default=False)

    # Новые поля для расширенной информации
    # ИСПРАВЛЕНО: mission удален отсюда (был дубликат)
    history_json = Column(JSON, nullable=True)  # История по годам
    contacts_json = Column(JSON, nullable=True)  # Соцсети, телефоны
    achievements = Column(Text, nullable=True)  # Статус из JSON

    # Связи
    programs = relationship("Program", back_populates="university", cascade="all, delete-orphan")
    faculties = relationship("Faculty", back_populates="university", cascade="all, delete-orphan")
    dormitories = relationship("Dormitory", back_populates="university", cascade="all, delete-orphan")
    grants = relationship("Grant", back_populates="university", cascade="all, delete-orphan")
    partnerships = relationship("Partnership", back_populates="university", cascade="all, delete-orphan")
    professions = relationship("Profession", secondary=university_professions, back_populates="universities")


class Faculty(Base):
    """Факультеты"""
    __tablename__ = "faculties"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)

    name_ru = Column(String, nullable=False)
    name_kz = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    dean_name = Column(String, nullable=True)
    dean_contacts = Column(String, nullable=True)

    website = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Связи
    university = relationship("University", back_populates="faculties")
    departments = relationship("Department", back_populates="faculty", cascade="all, delete-orphan")


class Department(Base):
    """Кафедры"""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    faculty_id = Column(Integer, ForeignKey("faculties.id"), nullable=False)

    name_ru = Column(String, nullable=False)
    name_kz = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    head_name = Column(String, nullable=True)  # Заведующий кафедрой
    specialization = Column(String, nullable=True)
    main_subjects = Column(JSON, nullable=True)  # Список основных дисциплин

    # Связи
    faculty = relationship("Faculty", back_populates="departments")


class Program(Base):
    """Образовательные программы"""
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculties.id"), nullable=True)

    code = Column(String, nullable=True, index=True)
    name_ru = Column(String, nullable=False, index=True)
    name_kz = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    degree = Column(Enum(DegreeType), nullable=False)
    duration = Column(Integer, nullable=True)  # Длительность в годах

    # Стоимость и финансы
    price = Column(Integer, nullable=True)
    currency = Column(String, default="KZT")

    # Поступление
    min_score = Column(Integer, nullable=True)
    language = Column(String, nullable=True)
    study_form = Column(String, nullable=True)  # очная, заочная, дистанционная

    # Дополнительная информация
    main_subjects = Column(JSON, nullable=True)
    credits = Column(Integer, nullable=True)

    # Аккредитация
    is_accredited = Column(Boolean, default=False)
    accreditation_body = Column(String, nullable=True)

    # Связи
    university = relationship("University", back_populates="programs")
    faculty = relationship("Faculty")


class Grant(Base):
    """Гранты и стипендии"""
    __tablename__ = "grants"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)

    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # government, university, private
    description = Column(Text, nullable=True)

    # Для абитуриентов
    available_for_applicants = Column(Boolean, default=True)
    applicants_count = Column(Integer, nullable=True)
    min_score_for_grant = Column(Integer, nullable=True)

    # Для студентов
    available_for_students = Column(Boolean, default=False)
    students_count = Column(Integer, nullable=True)
    amount = Column(Integer, nullable=True)

    requirements = Column(JSON, nullable=True)
    application_deadline = Column(Date, nullable=True)

    # Связи
    university = relationship("University", back_populates="grants")


class Dormitory(Base):
    """Общежития"""
    __tablename__ = "dormitories"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)

    name = Column(String, nullable=False)
    address = Column(String, nullable=True)

    capacity = Column(Integer, nullable=True)  # Количество мест
    occupied = Column(Integer, nullable=True)

    # Условия
    rooms_type = Column(String, nullable=True)  # 2-местные, 3-местные
    price_per_month = Column(Integer, nullable=True)

    # Удобства
    has_wifi = Column(Boolean, default=True)
    has_kitchen = Column(Boolean, default=False)
    has_laundry = Column(Boolean, default=False)
    has_gym = Column(Boolean, default=False)

    description = Column(Text, nullable=True)
    photos = Column(JSON, nullable=True)  # Список URL фотографий

    # Связи
    university = relationship("University", back_populates="dormitories")


class Partnership(Base):
    """Международное сотрудничество и партнерства"""
    __tablename__ = "partnerships"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)

    partner_name = Column(String, nullable=False)
    partner_country = Column(String, nullable=True)
    partner_type = Column(String, nullable=True)  # university, company, organization

    program_type = Column(String, nullable=True)  # exchange, double_degree, research
    description = Column(Text, nullable=True)

    start_date = Column(Date, nullable=True)
    website = Column(String, nullable=True)

    # Связи
    university = relationship("University", back_populates="partnerships")


class Favorite(Base):
    """Избранные университеты пользователей"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    created_at = Column(Date, default=datetime.utcnow)

    # Связи
    user = relationship("User", back_populates="favorites")
    university = relationship("University")


class Admission(Base):
    """Информация о поступлении"""
    __tablename__ = "admissions"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)

    degree = Column(Enum(DegreeType), nullable=False)

    # Сроки
    application_start = Column(Date, nullable=True)
    application_end = Column(Date, nullable=True)
    exam_dates = Column(JSON, nullable=True)

    # Требования
    required_documents = Column(JSON, nullable=True)
    min_score = Column(Integer, nullable=True)

    # Процесс
    application_process = Column(Text, nullable=True)
    contacts = Column(String, nullable=True)

    # Связи
    university = relationship("University")

# ============ ПРОФЕССИИ ============
class Profession(Base):
    """Справочник профессий/специальностей"""
    __tablename__ = "professions"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)  # Например: 6B06113
    name = Column(String, index=True, nullable=False)  # Программирование
    degree = Column(String)  # Бакалавриат/Магистратура/PhD
    
    # Связь с вузами
    universities = relationship("University", secondary=university_professions, back_populates="professions")

class CareerTestSession(Base):
    """Сессия профориентационного теста"""
    __tablename__ = "career_test_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Может быть анонимным
    
    difficulty = Column(String, default="medium") # easy, medium, hard
    total_questions = Column(Integer, default=10)
    current_step = Column(Integer, default=1)
    is_completed = Column(Boolean, default=False)
    created_at = Column(Date, default=datetime.utcnow)
    
    # Результаты (сохраним JSON ответа от AI)
    result_json = Column(JSON, nullable=True)

    # Связи
    answers = relationship("CareerTestAnswer", back_populates="session", cascade="all, delete-orphan")
    user = relationship("User", back_populates="career_sessions")


class CareerTestAnswer(Base):
    """Ответы пользователя внутри сессии"""
    __tablename__ = "career_test_answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("career_test_sessions.id"), nullable=False)
    
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)

    session = relationship("CareerTestSession", back_populates="answers")