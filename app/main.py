import uvicorn  # 👈 Добавлен импорт uvicorn
import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, universities, admin, ai, catalog

# Примечание: Исправление для Windows перенесено вниз, в блок main,
# чтобы не конфликтовать с авто-перезагрузкой.

app = FastAPI(
    title="University DataHub API",
    description="API для каталога университетов и образовательных программ",
    version="1.0.0"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://frontend:5173",  # Docker
        "*"  # Development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router)
app.include_router(universities.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(catalog.router)

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

# 👇 ДОБАВЛЕН КОД ДЛЯ ЗАПУСКА НА ПОРТУ 8080
if __name__ == "__main__":
    # Исправление для ошибки с asyncpg на Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Запуск сервера
    # host="0.0.0.0" делает сервер доступным в локальной сети
    # reload=True включает авто-перезагрузку при изменении кода
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)