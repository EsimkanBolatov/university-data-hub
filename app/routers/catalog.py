from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel

router = APIRouter(
    prefix="/catalog",
    tags=["Catalog"]
)

# Пример модели (можно заменить на SQLAlchemy)
class University(BaseModel):
    id: int
    name: str
    city: str

# Временные данные (потом заменишь на БД)
fake_universities = [
    University(id=1, name="KazNU", city="Almaty"),
    University(id=2, name="ITU", city="Istanbul"),
]

@router.get("/universities", response_model=List[University])
async def get_universities():
    return fake_universities

@router.get("/universities/{university_id}", response_model=University)
async def get_university(university_id: int):
    for uni in fake_universities:
        if uni.id == university_id:
            return uni
    raise HTTPException(status_code=404, detail="University not found")

@router.post("/universities", response_model=University)
async def add_university(university: University):
    fake_universities.append(university)
    return university

@router.get("/universities", response_model=List[University])
async def get_universities(query: str = None, city: str = None, min_rating: float = None, max_price: int = None):
    # фильтрация по параметрам
    results = fake_universities
    if query:
        results = [u for u in results if query.lower() in u.name.lower()]
    if city:
        results = [u for u in results if u.city == city]
    if min_rating:
        results = [u for u in results if u.rating >= min_rating]
    if max_price:
        results = [u for u in results if u.price <= max_price]
    return results
