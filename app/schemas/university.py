from pydantic import BaseModel, Field
from enum import Enum

class DegreeType(str, Enum):
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"

class LanguageType(str, Enum):
    RU = "ru"
    KZ = "kz"
    EN = "en"

class ProgramBase(BaseModel):
    code: str | None = None
    name: str
    degree: str
    duration: int | None = None
    language: str | None = None
    min_score: int | None = None
    price: int | None = Field(default=None, ge=0)


class ProgramCreate(ProgramBase):
    university_id: int


class ProgramResponse(ProgramBase):
    id: int
    university_id: int

    class Config:
        from_attributes = True


class UniversityBase(BaseModel):
    name_ru: str
    name_kz: str | None = None
    name_en: str | None = None
    description: str | None = None
    city: str
    address: str | None = None
    logo_url: str | None = None
    website: str | None = None
    virtual_tour_url: str | None = None
    rating: float = Field(default=0.0, ge=0, le=5)


class UniversityCreate(UniversityBase):
    pass


class UniversityResponse(UniversityBase):
    id: int
    programs: list[ProgramResponse] = []

    class Config:
        from_attributes = True


class UniversityListResponse(BaseModel):
    id: int
    name_ru: str
    city: str
    rating: float
    logo_url: str | None = None

    class Config:
        from_attributes = True