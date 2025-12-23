# scripts/test_skill_tree.py
import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import User, Skill, UserSkillProgress
from app.services.gamification_service import GamificationService

async def test_gamification():
    async with AsyncSessionLocal() as db:
        # Найти тестового пользователя
        user = await db.get(User, 1)
        
        # Симулировать завершение навыка
        skill = await db.get(Skill, 1)
        
        progress = UserSkillProgress(
            user_id=user.id,
            skill_id=skill.id,
            status="verified",
            score=100,
            progress_percentage=100
        )
        
        db.add(progress)
        await db.commit()
        
        # Проверить достижения
        new_achievements = await GamificationService.check_achievements(
            user.id, db
        )
        
        print(f"Новые достижения: {len(new_achievements)}")
        for ach in new_achievements:
            print(f"  - {ach['icon']} {ach['name']}")

asyncio.run(test_gamification())