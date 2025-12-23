# app/main.py
import uvicorn
import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.routers import auth, universities, admin, ai, catalog, career, resume_validator, skill_tree
from app.routers.favorites import router as favorites_router

app = FastAPI(
    title="University DataHub API",
    description="Комплексная платформа для каталогизации университетов Казахстана",
    version="2.0.0"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://frontend:5173",
        "*"
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
app.include_router(favorites_router) 
app.include_router(career.router) 
app.include_router(resume_validator.router)
app.include_router(skill_tree.router)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "University DataHub API v2.0",
        "features": [
            "AI-powered recommendations",
            "Advanced catalog filtering",
            "Smart comparison",
            "Favorites system",
            "Web search integration"
        ],
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)