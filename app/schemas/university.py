from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from enum import Enum


class UniversityTypeEnum(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNATIONAL = "international"


class DegreeTypeEnum(str, Enum):
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"


# ============= ДЕПАРТАМЕНТЫ/КАФЕДРЫ =============
class DepartmentBase(BaseModel):
    name_ru: str
    name_kz: Optional[str] = None
    description: Optional[str] = None
    head_name: Optional[str] = None
    specialization: Optional[str] = None
    main_subjects: Optional[List[str]] = None


class DepartmentResponse(DepartmentBase):
    id: int
    faculty_id: int

    class Config:
        from_attributes = True


# ============= ФАКУЛЬТЕТЫ =============
class FacultyBase(BaseModel):
    name_ru: str
    name_kz: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    dean_name: Optional[str] = None
    dean_contacts: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class FacultyCreate(FacultyBase):
    university_id: int


class FacultyResponse(FacultyBase):
    id: int
    university_id: int
    departments: List[DepartmentResponse] = []

    class Config:
        from_attributes = True


# ============= ПРОГРАММЫ =============
class ProgramBase(BaseModel):
    code: Optional[str] = None
    name_ru: str
    name_kz: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    degree: DegreeTypeEnum
    duration: Optional[int] = None
    price: Optional[int] = Field(default=None, ge=0)
    currency: str = "KZT"
    min_score: Optional[int] = None
    language: Optional[str] = None
    study_form: Optional[str] = None
    main_subjects: Optional[List[str]] = None
    credits: Optional[int] = None
    is_accredited: bool = False
    accreditation_body: Optional[str] = None


class ProgramCreate(ProgramBase):
    university_id: int
    faculty_id: Optional[int] = None


class ProgramResponse(ProgramBase):
    id: int
    university_id: int
    faculty_id: Optional[int] = None

    class Config:
        from_attributes = True


# ============= ГРАНТЫ =============
class GrantBase(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    available_for_applicants: bool = True
    applicants_count: Optional[int] = None
    min_score_for_grant: Optional[int] = None
    available_for_students: bool = False
    students_count: Optional[int] = None
    amount: Optional[int] = None
    requirements: Optional[dict] = None
    application_deadline: Optional[date] = None


class GrantCreate(GrantBase):
    university_id: int


class GrantResponse(GrantBase):
    id: int
    university_id: int

    class Config:
        from_attributes = True


# ============= ОБЩЕЖИТИЯ =============
class DormitoryBase(BaseModel):
    name: str
    address: Optional[str] = None
    capacity: Optional[int] = None
    occupied: Optional[int] = None
    rooms_type: Optional[str] = None
    price_per_month: Optional[int] = None
    has_wifi: bool = True
    has_kitchen: bool = False
    has_laundry: bool = False
    has_gym: bool = False
    description: Optional[str] = None
    photos: Optional[List[str]] = None


class DormitoryCreate(DormitoryBase):
    university_id: int


class DormitoryResponse(DormitoryBase):
    id: int
    university_id: int

    class Config:
        from_attributes = True


# ============= ПАРТНЕРСТВА =============
class PartnershipBase(BaseModel):
    partner_name: str
    partner_country: Optional[str] = None
    partner_type: Optional[str] = None
    program_type: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    website: Optional[str] = None


class PartnershipCreate(PartnershipBase):
    university_id: int


class PartnershipResponse(PartnershipBase):
    id: int
    university_id: int

    class Config:
        from_attributes = True


# ============= ПОСТУПЛЕНИЕ (НОВОЕ) =============
class AdmissionBase(BaseModel):
    degree: DegreeTypeEnum
    application_start: Optional[date] = None
    application_end: Optional[date] = None
    exam_dates: Optional[dict] = None
    required_documents: Optional[List[str]] = None
    min_score: Optional[int] = None
    application_process: Optional[str] = None
    contacts: Optional[str] = None


class AdmissionCreate(AdmissionBase):
    university_id: int


class AdmissionResponse(AdmissionBase):
    id: int
    university_id: int

    class Config:
        from_attributes = True


# ============= УНИВЕРСИТЕТЫ =============
class UniversityBase(BaseModel):
    # Основная информация
    name_ru: str
    name_kz: Optional[str] = None
    name_en: Optional[str] = None
    full_name: Optional[str] = None
    type: UniversityTypeEnum = UniversityTypeEnum.PUBLIC
    status: Optional[str] = None
    founded_year: Optional[int] = None

    # Местоположение
    city: str
    country: str = "Казахстан"
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Веб-ресурсы
    website: Optional[str] = None
    logo_url: Optional[str] = None
    virtual_tour_url: Optional[str] = None

    # Описание
    description: Optional[str] = None
    mission: Optional[str] = None
    values: Optional[str] = None
    history: Optional[str] = None

    # Рейтинги
    rating: float = Field(default=0.0, ge=0, le=5)
    national_ranking: Optional[int] = None
    international_ranking: Optional[int] = None

    # Руководство
    rector_name: Optional[str] = None
    rector_contacts: Optional[str] = None

    # Статистика
    total_students: Optional[int] = None
    international_students: Optional[int] = None
    total_teachers: Optional[int] = None
    doctors_count: Optional[int] = None
    phd_count: Optional[int] = None

    # Кампус
    campus_area: Optional[float] = None
    buildings_count: Optional[int] = None

    # Контакты
    phone: Optional[str] = None
    email: Optional[str] = None
    hotline: Optional[str] = None
    admission_phone: Optional[str] = None

    # Социальные сети
    telegram: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    facebook: Optional[str] = None

    # Дополнительно
    employment_rate: Optional[float] = None
    has_dormitory: bool = False
    has_military_department: bool = False


class UniversityCreate(UniversityBase):
    pass


class UniversityUpdate(BaseModel):
    name_ru: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None


class UniversityListResponse(BaseModel):
    id: int
    name_ru: str
    city: str
    type: str
    rating: float
    logo_url: Optional[str] = None
    has_dormitory: bool
    price_range: Optional[str] = None
    programs_count: Optional[int] = 0
    description: Optional[str] = None

    class Config:
        from_attributes = True


class UniversityDetailResponse(UniversityBase):
    id: int
    programs: List[ProgramResponse] = []
    faculties: List[FacultyResponse] = []
    grants: List[GrantResponse] = []
    dormitories: List[DormitoryResponse] = []
    partnerships: List[PartnershipResponse] = []

    class Config:
        from_attributes = True


# ============= СРАВНЕНИЕ =============
class UniversityCompareResponse(BaseModel):
    id: int
    name_ru: str
    city: str
    type: str
    rating: float
    total_students: Optional[int]
    programs_count: int
    min_price: Optional[int]
    max_price: Optional[int]
    has_dormitory: bool
    employment_rate: Optional[float]

    class Config:
        from_attributes = True


# ============= СТАТИСТИКА (НОВОЕ) =============
class UniversityStatsResponse(BaseModel):
    total_universities: int
    total_programs: int
    total_cities: int
    total_students: int
    average_tuition: int
    top_universities: List[dict]


# ============= ПОИСК =============
class SearchFilters(BaseModel):
    city: Optional[str] = None
    type: Optional[UniversityTypeEnum] = None
    has_dormitory: Optional[bool] = None
    min_rating: Optional[float] = None
    degree: Optional[DegreeTypeEnum] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    query: Optional[str] = None  # Полнотекстовый поиск