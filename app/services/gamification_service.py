"""
Сервис геймификации для Skill Tree
app/services/gamification_service.py

Фичи:
- Система уровней и опыта
- Достижения (achievements)
- Бейджи
- Лидерборды
- Стрики (streaks)
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path

from app.db.models import User
from app.db.models_skill import UserSkillProgress, SkillMaterial, ChallengeSubmission
from app.services.ai_service import AIComponents
from app.core.config import settings


class Achievement:
    """Определение достижения"""
    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        icon: str,
        condition: callable,
        points: int,
        rarity: str = "common"  # common, rare, epic, legendary
    ):
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon
        self.condition = condition
        self.points = points
        self.rarity = rarity


class GamificationService:
    """Сервис геймификации"""
    
    # Таблица уровней (опыт -> уровень)
    LEVEL_THRESHOLDS = [
        0,      # Level 1
        100,    # Level 2
        300,    # Level 3
        600,    # Level 4
        1000,   # Level 5
        1500,   # Level 6
        2200,   # Level 7
        3000,   # Level 8
        4000,   # Level 9
        5200,   # Level 10
        6600,   # Level 11
        8200,   # Level 12
        10000,  # Level 13
        12000,  # Level 14
        14500,  # Level 15
        17500,  # Level 16
        21000,  # Level 17
        25000,  # Level 18
        30000,  # Level 19
        36000,  # Level 20
    ]
    
    # Список всех достижений
    ACHIEVEMENTS = [
        Achievement(
            id="first_skill",
            name="Первый шаг",
            description="Завершите ваш первый навык",
            icon="🎯",
            condition=lambda stats: stats["completed_skills"] >= 1,
            points=50,
            rarity="common"
        ),
        Achievement(
            id="skill_master_10",
            name="Мастер навыков",
            description="Завершите 10 навыков",
            icon="⭐",
            condition=lambda stats: stats["completed_skills"] >= 10,
            points=200,
            rarity="rare"
        ),
        Achievement(
            id="skill_master_50",
            name="Гуру",
            description="Завершите 50 навыков",
            icon="🏆",
            condition=lambda stats: stats["completed_skills"] >= 50,
            points=1000,
            rarity="epic"
        ),
        Achievement(
            id="challenge_winner",
            name="Победитель челленджа",
            description="Успешно завершите ваш первый челлендж",
            icon="💪",
            condition=lambda stats: stats["challenges_completed"] >= 1,
            points=100,
            rarity="common"
        ),
        Achievement(
            id="challenge_master",
            name="Мастер челленджей",
            description="Завершите 10 челленджей",
            icon="🥇",
            condition=lambda stats: stats["challenges_completed"] >= 10,
            points=500,
            rarity="epic"
        ),
        Achievement(
            id="contributor",
            name="Вкладчик",
            description="Добавьте 5 материалов в wiki",
            icon="📚",
            condition=lambda stats: stats["materials_contributed"] >= 5,
            points=150,
            rarity="rare"
        ),
        Achievement(
            id="popular_author",
            name="Популярный автор",
            description="Получите 100+ лайков на ваших материалах",
            icon="❤️",
            condition=lambda stats: stats["total_likes"] >= 100,
            points=300,
            rarity="rare"
        ),
        Achievement(
            id="perfect_score",
            name="Идеальная работа",
            description="Получите 100 баллов за челлендж",
            icon="💯",
            condition=lambda stats: stats["max_challenge_score"] >= 100,
            points=200,
            rarity="rare"
        ),
        Achievement(
            id="week_streak",
            name="Неделя подряд",
            description="Учитесь 7 дней подряд",
            icon="🔥",
            condition=lambda stats: stats["current_streak"] >= 7,
            points=100,
            rarity="common"
        ),
        Achievement(
            id="month_streak",
            name="Месяц упорства",
            description="Учитесь 30 дней подряд",
            icon="🔥🔥",
            condition=lambda stats: stats["current_streak"] >= 30,
            points=500,
            rarity="epic"
        ),
        Achievement(
            id="early_bird",
            name="Ранняя птичка",
            description="Завершите 10 навыков до 9:00",
            icon="🌅",
            condition=lambda stats: stats["early_completions"] >= 10,
            points=150,
            rarity="rare"
        ),
        Achievement(
            id="night_owl",
            name="Сова",
            description="Завершите 10 навыков после 22:00",
            icon="🦉",
            condition=lambda stats: stats["late_completions"] >= 10,
            points=150,
            rarity="rare"
        ),
        Achievement(
            id="soft_skills_champion",
            name="Чемпион Soft Skills",
            description="Завершите все глобальные Soft Skills",
            icon="🎭",
            condition=lambda stats: stats["soft_skills_completed"] >= stats["total_soft_skills"],
            points=1000,
            rarity="legendary"
        ),
        Achievement(
            id="speed_learner",
            name="Скоростное обучение",
            description="Завершите навык за < 50% от оценочного времени",
            icon="⚡",
            condition=lambda stats: stats["has_speed_completion"],
            points=200,
            rarity="rare"
        )
    ]

    @staticmethod
    async def get_user_stats(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """Собрать все статистики пользователя"""
        
        # 1. Завершённые навыки
        completed_skills = await db.scalar(
            select(func.count(UserSkillProgress.id)).where(
                and_(
                    UserSkillProgress.user_id == user_id,
                    UserSkillProgress.status == "verified"
                )
            )
        ) or 0
        
        # 2. Soft Skills
        soft_skills_query = select(func.count(UserSkillProgress.id)).join(
            UserSkillProgress.skill
        ).where(
            and_(
                UserSkillProgress.user_id == user_id,
                UserSkillProgress.status == "verified",
                UserSkillProgress.skill.has(is_global=True)
            )
        )
        soft_skills_completed = await db.scalar(soft_skills_query) or 0
        
        # Всего Soft Skills в системе
        from app.db.models_skill import Skill
        total_soft_skills = await db.scalar(
            select(func.count(Skill.id)).where(Skill.is_global == True)
        ) or 1
        
        # 3. Челленджи
        challenges_completed = await db.scalar(
            select(func.count(ChallengeSubmission.id)).where(
                and_(
                    ChallengeSubmission.user_id == user_id,
                    ChallengeSubmission.status == "approved"
                )
            )
        ) or 0
        
        # Максимальный балл
        max_challenge_score = await db.scalar(
            select(func.max(ChallengeSubmission.score)).where(
                and_(
                    ChallengeSubmission.user_id == user_id,
                    ChallengeSubmission.status == "approved"
                )
            )
        ) or 0
        
        # 4. Вклад в wiki
        materials_contributed = await db.scalar(
            select(func.count(SkillMaterial.id)).where(
                SkillMaterial.author_id == user_id
            )
        ) or 0
        
        # Лайки на материалах
        total_likes = await db.scalar(
            select(func.sum(SkillMaterial.rating)).where(
                SkillMaterial.author_id == user_id
            )
        ) or 0
        
        # 5. Стрики (streak)
        current_streak = await GamificationService._calculate_streak(user_id, db)
        
        # 6. Время завершения (early/late)
        early_completions = 0  # TODO: реализовать через анализ verified_at
        late_completions = 0   # TODO
        
        # 7. Скоростные завершения
        has_speed_completion = False  # TODO: сравнить actual_time vs estimated_hours
        
        # 8. Общий опыт
        total_experience = await db.scalar(
            select(func.sum(UserSkillProgress.score)).where(
                UserSkillProgress.user_id == user_id
            )
        ) or 0
        
        return {
            "completed_skills": completed_skills,
            "soft_skills_completed": soft_skills_completed,
            "total_soft_skills": total_soft_skills,
            "challenges_completed": challenges_completed,
            "max_challenge_score": max_challenge_score,
            "materials_contributed": materials_contributed,
            "total_likes": total_likes,
            "current_streak": current_streak,
            "early_completions": early_completions,
            "late_completions": late_completions,
            "has_speed_completion": has_speed_completion,
            "total_experience": total_experience
        }

    @staticmethod
    async def check_achievements(user_id: int, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Проверить и вернуть новые достижения
        
        Returns: список новых незаблокированных достижений
        """
        
        # Получаем статистику
        stats = await GamificationService.get_user_stats(user_id, db)
        
        # Получаем уже разблокированные достижения
        user = await db.get(User, user_id)
        unlocked_ids = user.achievements_json.get("unlocked", []) if hasattr(user, "achievements_json") and user.achievements_json else []
        
        # Проверяем каждое достижение
        new_achievements = []
        
        for achievement in GamificationService.ACHIEVEMENTS:
            if achievement.id in unlocked_ids:
                continue  # Уже разблокировано
            
            # Проверяем условие
            if achievement.condition(stats):
                new_achievements.append({
                    "id": achievement.id,
                    "name": achievement.name,
                    "description": achievement.description,
                    "icon": achievement.icon,
                    "points": achievement.points,
                    "rarity": achievement.rarity,
                    "unlocked_at": datetime.utcnow().isoformat()
                })
        
        return new_achievements

    @staticmethod
    async def unlock_achievement(
        user_id: int,
        achievement_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Разблокировать достижение для пользователя"""
        
        user = await db.get(User, user_id)
        if not user:
            return {"error": "User not found"}
        
        # Ищем достижение
        achievement = next(
            (a for a in GamificationService.ACHIEVEMENTS if a.id == achievement_id),
            None
        )
        
        if not achievement:
            return {"error": "Achievement not found"}
        
        # Инициализируем achievements_json если нет
        if not hasattr(user, "achievements_json") or not user.achievements_json:
            user.achievements_json = {"unlocked": [], "points": 0}
        
        # Проверяем, не разблокировано ли уже
        if achievement_id in user.achievements_json.get("unlocked", []):
            return {"error": "Already unlocked"}
        
        # Разблокируем
        if "unlocked" not in user.achievements_json:
            user.achievements_json["unlocked"] = []
        
        user.achievements_json["unlocked"].append(achievement_id)
        user.achievements_json["points"] = user.achievements_json.get("points", 0) + achievement.points
        
        await db.commit()
        
        return {
            "success": True,
            "achievement": {
                "id": achievement.id,
                "name": achievement.name,
                "icon": achievement.icon,
                "points": achievement.points
            }
        }

    @staticmethod
    def calculate_level(experience: int) -> Dict[str, Any]:
        """
        Рассчитать уровень по опыту
        
        Returns:
        {
            "level": 5,
            "current_exp": 1200,
            "exp_for_level": 1000,
            "exp_for_next": 1500,
            "progress_to_next": 40.0
        }
        """
        
        level = 1
        for threshold in GamificationService.LEVEL_THRESHOLDS:
            if experience >= threshold:
                level += 1
            else:
                break
        
        level = min(level - 1, len(GamificationService.LEVEL_THRESHOLDS) - 1)
        
        exp_for_level = GamificationService.LEVEL_THRESHOLDS[level - 1] if level > 1 else 0
        exp_for_next = GamificationService.LEVEL_THRESHOLDS[level] if level < len(GamificationService.LEVEL_THRESHOLDS) else exp_for_level + 10000
        
        progress = ((experience - exp_for_level) / (exp_for_next - exp_for_level) * 100) if exp_for_next > exp_for_level else 100
        
        return {
            "level": level,
            "current_exp": experience,
            "exp_for_level": exp_for_level,
            "exp_for_next": exp_for_next,
            "progress_to_next": round(progress, 1)
        }

    @staticmethod
    async def get_leaderboard(
        db: AsyncSession,
        period: str = "all_time",  # all_time, month, week
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получить лидерборд
        
        Сортировка по:
        1. Общему опыту
        2. Количеству завершённых навыков
        """
        
        # Базовый запрос
        query = select(
            User.id,
            User.full_name,
            User.email,
            func.sum(UserSkillProgress.score).label("total_exp"),
            func.count(UserSkillProgress.id).label("skills_completed")
        ).join(
            UserSkillProgress, UserSkillProgress.user_id == User.id
        ).where(
            UserSkillProgress.status == "verified"
        ).group_by(
            User.id, User.full_name, User.email
        )
        
        # Фильтр по периоду
        if period == "month":
            month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            query = query.where(UserSkillProgress.verified_at >= month_ago)
        elif period == "week":
            week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            query = query.where(UserSkillProgress.verified_at >= week_ago)
        
        # Сортировка и лимит
        query = query.order_by(desc("total_exp")).limit(limit)
        
        result = await db.execute(query)
        rows = result.all()
        
        leaderboard = []
        for rank, row in enumerate(rows, 1):
            level_info = GamificationService.calculate_level(row.total_exp or 0)
            
            leaderboard.append({
                "rank": rank,
                "user_id": row.id,
                "username": row.full_name,
                "email": row.email,
                "total_experience": row.total_exp or 0,
                "level": level_info["level"],
                "skills_completed": row.skills_completed
            })
        
        return leaderboard

    @staticmethod
    async def _calculate_streak(user_id: int, db: AsyncSession) -> int:
        """
        Рассчитать текущий streak пользователя
        (сколько дней подряд пользователь завершал навыки)
        """
        
        # Получаем даты завершения навыков (уникальные дни)
        query = select(
            func.date(UserSkillProgress.completed_at).label("completion_date")
        ).where(
            and_(
                UserSkillProgress.user_id == user_id,
                UserSkillProgress.status == "verified",
                UserSkillProgress.completed_at.isnot(None)
            )
        ).distinct().order_by(desc("completion_date"))
        
        result = await db.execute(query)
        dates = [row[0] for row in result.all()]
        
        if not dates:
            return 0
        
        # Проверяем streak
        streak = 0
        today = datetime.utcnow().date()
        
        for i, date_str in enumerate(dates):
            if isinstance(date_str, str):
                date = datetime.fromisoformat(date_str).date()
            else:
                date = date_str
            
            expected_date = today - timedelta(days=i)
            
            if date == expected_date:
                streak += 1
            else:
                break
        
        return streak

    @staticmethod
    async def generate_personalized_recommendations(
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        AI рекомендации следующих навыков для изучения
        
        На основе:
        - Текущего прогресса
        - Популярности навыков
        - Prerequisites
        - Интересов пользователя
        """
        
        stats = await GamificationService.get_user_stats(user_id, db)
        
        # Получаем завершённые навыки
        completed_query = select(UserSkillProgress.skill_id).where(
            and_(
                UserSkillProgress.user_id == user_id,
                UserSkillProgress.status == "verified"
            )
        )
        result = await db.execute(completed_query)
        completed_ids = [row[0] for row in result.all()]
        
        # Формируем промпт для AI
        client = AIComponents.get_openai()
        
        prompt = f"""
Студент завершил {stats['completed_skills']} навыков.
ID завершённых: {completed_ids[:10]}...

Задача: порекомендовать 5 следующих навыков для изучения.

Критерии:
1. Логическая последовательность (prerequisites)
2. Оптимальная сложность (не слишком легко, не слишком сложно)
3. Популярные навыки в индустрии
4. Разнообразие (не только технические)

Верни JSON:
{{
    "recommendations": [
        {{
            "skill_name": "...",
            "reason": "почему рекомендуем",
            "priority": "high/medium/low",
            "estimated_time": "часов"
        }}
    ]
}}
"""

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            response_format={"type": "json_object"}
        )
        
        import json
        return json.loads(response.choices[0].message.content)