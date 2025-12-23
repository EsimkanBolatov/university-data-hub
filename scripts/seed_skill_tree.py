# scripts/seed_skill_tree.py
import asyncio
from app.db.database import AsyncSessionLocal
from app.services.syllabus_parser_service import SyllabusParserService

async def seed():
    async with AsyncSessionLocal() as db:
        # Генерация Soft Skills
        count = await SyllabusParserService.generate_soft_skills(db)
        print(f"✅ Создано {count} Soft Skills")

if __name__ == "__main__":
    asyncio.run(seed())