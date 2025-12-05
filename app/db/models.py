import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class RoleEnum(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """Пользователи системы"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.USER)


class University(Base):
    """Университеты"""
    __tablename__ = "universities"

    id = Column(Integer, primary_key=True, index=True)
    name_ru = Column(String, nullable=False)
    name_kz = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    city = Column(String, nullable=False, index=True)
    address = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    website = Column(String, nullable=True)
    rating = Column(Float, default=0.0)
    virtual_tour_url = Column(String, nullable=True)

    # Связь с программами
    programs = relationship("Program", back_populates="university")


class Program(Base):
    """Образовательные программы"""
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    code = Column(String, nullable=True)  # Например, "6B06101"
    name = Column(String, nullable=False)
    degree = Column(String, nullable=False)  # bachelor, master, phd
    price = Column(Integer, nullable=True)  # Цена в тенге
    duration = Column(Integer, nullable=True)  # Длительность в годах
    language = Column(String, nullable=True)  # ru, kz, en
    min_score = Column(Integer, nullable=True)  # Проходной балл

    # Связь с университетом
    university = relationship("University", back_populates="programs")