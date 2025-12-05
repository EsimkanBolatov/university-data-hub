from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, universities

app = FastAPI(
    title="University DataHub API",
    description="API для каталога университетов и образовательных программ",
    version="1.0.0"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router)
app.include_router(universities.router)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "University DataHub API is running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}