from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

class NotificationService:
    @staticmethod
    async def get_user_notifications(user_id: int, db: AsyncSession, unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        # Placeholder implementation
        return []

    @staticmethod
    async def mark_as_read(user_id: int, notification_id: str, db: AsyncSession) -> bool:
        return True

    @staticmethod
    async def mark_all_as_read(user_id: int, db: AsyncSession) -> int:
        return 0

    @staticmethod
    def achievement_unlocked(achievement_id: str, name: str, icon: str, points: int) -> Dict[str, Any]:
        return {
            "type": "achievement_unlocked",
            "title": "Достижение разблокировано!",
            "message": f"Вы получили достижение {name}",
            "priority": "high"
        }

    @staticmethod
    def material_approved(material_id: int, material_title: str) -> Dict[str, Any]:
        return {
            "type": "material_approved",
            "title": "Материал одобрен",
            "message": f"Ваш материал '{material_title}' был одобрен модератором.",
            "priority": "normal"
        }

    @staticmethod
    def challenge_checked(challenge_id: int, submission_id: int, status: str, score: int, feedback: str) -> Dict[str, Any]:
         return {
            "type": "challenge_checked",
            "title": "Челлендж проверен",
            "message": f"Статус: {status}. Баллы: {score}",
            "priority": "high"
        }

    @staticmethod
    def level_up(new_level: int, rewards: List[str]) -> Dict[str, Any]:
         return {
            "type": "level_up",
            "title": "Повышение уровня!",
            "message": f"Вы достигли уровня {new_level}",
            "priority": "high"
        }

    @staticmethod
    async def send_notification(user_id: int, notification: Dict[str, Any], db: AsyncSession, channels: List[str] = None):
        pass