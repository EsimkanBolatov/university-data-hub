"""
API роутер для геймификации и уведомлений
app/routers/gamification.py
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional

from app.db.database import get_db
from app.dependencies import get_current_user
from app.db.models import User
from app.services.gamification_service import GamificationService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/gamification", tags=["Gamification & Achievements"])


# ============= СХЕМЫ =============

class UserStatsResponse(BaseModel):
    """Статистика пользователя"""
    completed_skills: int
    soft_skills_completed: int
    challenges_completed: int
    materials_contributed: int
    total_likes: int
    current_streak: int
    total_experience: int
    level_info: dict


class AchievementResponse(BaseModel):
    """Достижение"""
    id: str
    name: str
    description: str
    icon: str
    points: int
    rarity: str
    unlocked: bool
    unlocked_at: Optional[str] = None


class LeaderboardEntry(BaseModel):
    """Запись в лидерборде"""
    rank: int
    user_id: int
    username: str
    total_experience: int
    level: int
    skills_completed: int


class NotificationResponse(BaseModel):
    """Уведомление"""
    id: str
    type: str
    title: str
    message: str
    priority: str
    read: bool
    created_at: str
    action_url: Optional[str] = None


# ============= СТАТИСТИКА И УРОВНИ =============

@router.get("/stats", response_model=UserStatsResponse)
async def get_my_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить мою статистику и уровень"""
    
    stats = await GamificationService.get_user_stats(current_user.id, db)
    level_info = GamificationService.calculate_level(stats["total_experience"])
    
    return UserStatsResponse(
        completed_skills=stats["completed_skills"],
        soft_skills_completed=stats["soft_skills_completed"],
        challenges_completed=stats["challenges_completed"],
        materials_contributed=stats["materials_contributed"],
        total_likes=stats["total_likes"],
        current_streak=stats["current_streak"],
        total_experience=stats["total_experience"],
        level_info=level_info
    )


@router.get("/level/{experience}")
async def calculate_level(experience: int = Path(..., ge=0)):
    """Рассчитать уровень по опыту"""
    return GamificationService.calculate_level(experience)


# ============= ДОСТИЖЕНИЯ =============

@router.get("/achievements", response_model=List[AchievementResponse])
async def get_my_achievements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить все достижения (разблокированные и заблокированные)"""
    
    # Получаем статистику
    stats = await GamificationService.get_user_stats(current_user.id, db)
    
    # Получаем разблокированные
    unlocked_ids = []
    if hasattr(current_user, "achievements_json") and current_user.achievements_json:
        unlocked_ids = current_user.achievements_json.get("unlocked", [])
    
    achievements = []
    
    for ach in GamificationService.ACHIEVEMENTS:
        # Проверяем условие для отображения прогресса
        is_unlocked = ach.id in unlocked_ids
        
        achievements.append(AchievementResponse(
            id=ach.id,
            name=ach.name,
            description=ach.description,
            icon=ach.icon,
            points=ach.points,
            rarity=ach.rarity,
            unlocked=is_unlocked,
            unlocked_at=None  # TODO: добавить timestamp из БД
        ))
    
    return achievements


@router.post("/achievements/check")
async def check_new_achievements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Проверить новые достижения
    Вызывается автоматически после завершения навыка/челленджа
    """
    
    new_achievements = await GamificationService.check_achievements(
        current_user.id,
        db
    )
    
    # Разблокируем новые
    unlocked = []
    for ach in new_achievements:
        result = await GamificationService.unlock_achievement(
            current_user.id,
            ach["id"],
            db
        )
        
        if result.get("success"):
            unlocked.append(result["achievement"])
            
            # Отправляем уведомление
            notification = NotificationService.achievement_unlocked(
                ach["id"],
                ach["name"],
                ach["icon"],
                ach["points"]
            )
            
            await NotificationService.send_notification(
                current_user.id,
                notification,
                db,
                channels=["in_app", "push"]
            )
    
    return {
        "new_achievements": unlocked,
        "count": len(unlocked)
    }


# ============= ЛИДЕРБОРД =============

@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    period: str = Query("all_time", regex="^(all_time|month|week)$"),
    limit: int = Query(100, ge=10, le=500),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить лидерборд
    
    Периоды:
    - all_time: за всё время
    - month: за последний месяц
    - week: за последнюю неделю
    """
    
    leaderboard = await GamificationService.get_leaderboard(db, period, limit)
    
    return [LeaderboardEntry(**entry) for entry in leaderboard]


@router.get("/leaderboard/my-position")
async def get_my_leaderboard_position(
    period: str = Query("all_time", regex="^(all_time|month|week)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Узнать свою позицию в лидерборде"""
    
    leaderboard = await GamificationService.get_leaderboard(db, period, 1000)
    
    my_position = next(
        (entry for entry in leaderboard if entry["user_id"] == current_user.id),
        None
    )
    
    if not my_position:
        return {
            "rank": None,
            "message": "Вы ещё не в топе. Завершите навыки, чтобы попасть в рейтинг!"
        }
    
    return my_position


# ============= РЕКОМЕНДАЦИИ =============

@router.get("/recommendations")
async def get_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI рекомендации следующих навыков для изучения"""
    
    recommendations = await GamificationService.generate_personalized_recommendations(
        current_user.id,
        db
    )
    
    return recommendations


# ============= УВЕДОМЛЕНИЯ =============

@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить уведомления"""
    
    notifications = await NotificationService.get_user_notifications(
        current_user.id,
        db,
        unread_only,
        limit
    )
    
    return [NotificationResponse(**n) for n in notifications]


@router.get("/notifications/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Количество непрочитанных уведомлений"""
    
    if not hasattr(current_user, "notifications_json") or not current_user.notifications_json:
        return {"count": 0}
    
    return {
        "count": current_user.notifications_json.get("unread_count", 0)
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отметить уведомление как прочитанное"""
    
    success = await NotificationService.mark_as_read(
        current_user.id,
        notification_id,
        db
    )
    
    if not success:
        raise HTTPException(404, "Уведомление не найдено")
    
    return {"message": "Отмечено как прочитанное"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отметить все уведомления как прочитанные"""
    
    count = await NotificationService.mark_all_as_read(current_user.id, db)
    
    return {
        "message": f"Отмечено {count} уведомлений",
        "count": count
    }


# ============= ТЕСТОВЫЕ ЭНДПОИНТЫ =============

@router.post("/test/send-notification")
async def test_send_notification(
    notification_type: str = Query(..., regex="^(material_approved|challenge_checked|achievement_unlocked|level_up)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Тестовая отправка уведомления (для разработки)"""
    
    if notification_type == "material_approved":
        notification = NotificationService.material_approved(
            material_id=1,
            material_title="Тестовый материал"
        )
    elif notification_type == "challenge_checked":
        notification = NotificationService.challenge_checked(
            challenge_id=1,
            submission_id=1,
            status="approved",
            score=95,
            feedback="Отличная работа!"
        )
    elif notification_type == "achievement_unlocked":
        notification = NotificationService.achievement_unlocked(
            achievement_id="first_skill",
            achievement_name="Первый шаг",
            achievement_icon="🎯",
            points=50
        )
    else:  # level_up
        notification = NotificationService.level_up(
            new_level=5,
            rewards=["Новый бейдж", "50 XP бонус"]
        )
    
    result = await NotificationService.send_notification(
        current_user.id,
        notification,
        db,
        channels=["in_app"]
    )
    
    return result


@router.post("/test/simulate-level-up")
async def test_simulate_level_up(
    target_level: int = Query(..., ge=2, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Симулировать повышение уровня (для тестирования)
    ТОЛЬКО для разработки!
    """
    
    # Находим нужный опыт
    required_exp = GamificationService.LEVEL_THRESHOLDS[target_level - 1]
    
    # Обновляем статистику пользователя (фейковые данные)
    # В реальности опыт начисляется через завершение навыков
    
    level_info = GamificationService.calculate_level(required_exp)
    
    # Отправляем уведомление
    notification = NotificationService.level_up(
        new_level=target_level,
        rewards=["Тестовая награда", f"+{target_level * 10} бонус XP"]
    )
    
    await NotificationService.send_notification(
        current_user.id,
        notification,
        db,
        channels=["in_app", "push"]
    )
    
    return {
        "message": f"Симулировано повышение до уровня {target_level}",
        "required_experience": required_exp,
        "level_info": level_info
    }