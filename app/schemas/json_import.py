from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any, Dict, List, Union

# --- Вспомогательные модели ---

class GeoCoords(BaseModel):
    lat: Optional[float] = Field(alias="широта", default=None)
    lon: Optional[float] = Field(alias="долгота", default=None)

class MainInfoSchema(BaseModel):
    # Алиасы соответствуют ключам в JSON (уже очищенным от цифр)
    name: Optional[str] = Field(alias="Название_университета", default=None)
    full_name: Optional[str] = Field(alias="Полное_название", default=None)
    type: Optional[str] = Field(alias="Тип", default="public")
    founded_year: Optional[Union[int, str]] = Field(alias="Год_основания", default=None)
    
    # Сложное поле: может быть строкой или словарем
    city_raw: Optional[Union[str, Dict[str, Any]]] = Field(alias="Город_страна", default=None)
    
    address: Optional[str] = Field(alias="Адрес", default=None)
    website: Optional[str] = Field(alias="Официальный_сайт", default=None)
    logo: Optional[str] = Field(alias="Логотип", default=None)
    status: Optional[str] = Field(alias="Статус", default=None)
    coords: Optional[GeoCoords] = Field(alias="Геокоординаты", default=None)

    # Валидатор для года (если придет строка "1992 г.")
    @field_validator('founded_year', mode='before')
    def parse_year(cls, v):
        if isinstance(v, str):
            import re
            nums = re.findall(r'\d{4}', v)
            return int(nums[0]) if nums else None
        return v

    @property
    def city_parsed(self) -> str:
        """Извлекает название города из любого формата"""
        if isinstance(self.city_raw, dict):
            return self.city_raw.get("город", "Неизвестно")
        if isinstance(self.city_raw, str):
            # Если "Алматы, Казахстан" -> берем до запятой
            return self.city_raw.split(',')[0].strip()
        return "Неизвестно"
    
    @property
    def country_parsed(self) -> str:
        if isinstance(self.city_raw, dict):
            return self.city_raw.get("страна", "Казахстан")
        if isinstance(self.city_raw, str) and "," in self.city_raw:
             return self.city_raw.split(',')[1].strip()
        return "Казахстан"

class DescriptionSchema(BaseModel):
    short_text: Optional[str] = Field(alias="Короткий_текст", default=None)
    mission: Optional[str] = Field(alias="Миссия", default=None)

class ContactSchema(BaseModel):
    phone: Optional[str] = Field(alias="Телефон", default=None)
    email: Optional[str] = Field(alias="Email", default=None)
    socials: Optional[Dict[str, str]] = Field(alias="Социальные_сети", default_factory=dict)

# --- Основная модель файла ---

class UniversityImportSchema(BaseModel):
    # Мы используем очищенные ключи (без "1_", "2_" и т.д.)
    info: Optional[MainInfoSchema] = Field(alias="Основная_информация", default=None)
    desc: Optional[DescriptionSchema] = Field(alias="Краткое_описание", default=None)
    history: Optional[Dict[str, Any]] = Field(alias="История", default=None)
    contacts: Optional[ContactSchema] = Field(alias="Контакты", default=None)
    
    # Список профессий (в UIB файле он не найден, но может быть в других)
    professions: List[str] = Field(alias="Список_всех_профессий_и_специальностей", default_factory=list)

    class Config:
        extra = "ignore" # Игнорировать неизвестные поля, чтобы не падать