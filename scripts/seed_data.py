"""
Скрипт для создания тестовых пользователей (Admin и User)
Запуск: python -m scripts.create_users
"""
import asyncio
import sys
import os

# Добавляем корневую папку проекта в sys.path, чтобы Python видел модуль app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.core.security import get_password_hash
from sqlalchemy.exc import IntegrityError

async def create_users():
    """Создать тестовых пользователей"""

    # Открываем сессию
    async with AsyncSessionLocal() as db:
        print("🚀 Начинаю создание пользователей...")

        users = [
            User(
                email="admin@university.kz",
                password_hash=get_password_hash("admin123"),
                full_name="Администратор",
                role="admin"
            ),
            User(
                email="student@gmail.com",
                password_hash=get_password_hash("student123"),
                full_name="Айдар Нурланов",
                role="user"
            )
        ]

        try:
            # Добавляем всех в сессию
            db.add_all(users)

            # Сохраняем изменения в БД
            await db.commit()

            print("✅ Пользователи успешно созданы:")
            print("   1. admin@university.kz (пароль: admin123)")
            print("   2. student@gmail.com   (пароль: student123)")

        except IntegrityError:
            # Если пользователи с таким email уже есть, откатываем изменения
            await db.rollback()
            print("⚠️ Ошибка: Пользователи с таким email уже существуют.")
        except Exception as e:
            await db.rollback()
            print(f"❌ Произошла ошибка: {e}")

if __name__ == "__main__":
    # Фикс для Windows (обязателен для работы asyncpg)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(create_users())