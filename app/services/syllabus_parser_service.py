"""
AI Сервис для парсинга учебных планов в дерево навыков
app/services/syllabus_parser_service.py
"""
import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pypdf
from pathlib import Path

from app.services.ai_service import AIComponents
from app.core.config import settings
from app.db.models import Profession
from app.db.models_skill import Skill


class SyllabusParserService:
    """Парсинг PDF учебных планов в дерево навыков"""

    @staticmethod
    async def parse_pdf_to_tree(
        file_path: str,
        specialty_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Основная функция парсинга
        
        Процесс:
        1. Читает PDF
        2. Извлекает текст
        3. Отправляет в GPT для структуризации
        4. Создаёт иерархию навыков в БД
        """
        
        # 1. Чтение PDF
        try:
            text_content = await SyllabusParserService._extract_text_from_pdf(file_path)
        except Exception as e:
            return {
                "status": "error",
                "errors": [f"Ошибка чтения PDF: {str(e)}"],
                "skills_created": 0,
                "tree_structure": []
            }

        # 2. Проверка специальности
        specialty = await db.get(Profession, specialty_id)
        if not specialty:
            return {
                "status": "error",
                "errors": ["Специальность не найдена"],
                "skills_created": 0,
                "tree_structure": []
            }

        # 3. AI парсинг структуры
        try:
            tree_data = await SyllabusParserService._ai_parse_syllabus(
                text_content,
                specialty.name
            )
        except Exception as e:
            return {
                "status": "error",
                "errors": [f"Ошибка AI парсинга: {str(e)}"],
                "skills_created": 0,
                "tree_structure": []
            }

        # 4. Создание навыков в БД
        try:
            created_count = await SyllabusParserService._create_skills_hierarchy(
                tree_data,
                specialty_id,
                file_path,
                db
            )
            
            await db.commit()
            
            return {
                "status": "success",
                "skills_created": created_count,
                "tree_structure": tree_data,
                "warnings": []
            }
            
        except Exception as e:
            await db.rollback()
            return {
                "status": "error",
                "errors": [f"Ошибка создания навыков: {str(e)}"],
                "skills_created": 0,
                "tree_structure": tree_data
            }

    @staticmethod
    async def _extract_text_from_pdf(file_path: str) -> str:
        """Извлечение текста из PDF"""
        reader = pypdf.PdfReader(file_path)
        
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text())
        
        full_text = "\n\n".join(text_parts)
        
        # Ограничиваем длину для GPT (примерно 15000 токенов)
        if len(full_text) > 60000:
            full_text = full_text[:60000] + "\n...(обрезано)"
        
        return full_text

    @staticmethod
    async def _ai_parse_syllabus(text: str, specialty_name: str) -> List[Dict[str, Any]]:
        """
        Парсинг через GPT-4
        
        Возвращает иерархию:
        [
            {
                "name": "Программирование",
                "description": "...",
                "level": 1,
                "estimated_hours": 120,
                "children": [
                    {
                        "name": "Python Основы",
                        "level": 1,
                        "estimated_hours": 40,
                        "children": []
                    }
                ]
            }
        ]
        """
        client = AIComponents.get_openai()

        system_prompt = f"""
Ты методист и эксперт по созданию учебных программ.
Твоя задача: проанализировать учебный план специальности "{specialty_name}" 
и разбить его на иерархию навыков.

ТРЕБОВАНИЯ К СТРУКТУРЕ:
1. Уровень 1: Разделы (например, "Программирование", "Базы данных")
2. Уровень 2: Темы (например, "Python", "PostgreSQL")
3. Уровень 3: Конкретные навыки (например, "Циклы в Python", "SQL запросы")

ТРЕБОВАНИЯ К ДАННЫМ:
- name: краткое название (до 100 символов)
- description: описание что студент научится делать
- level: сложность 1-5
- estimated_hours: примерное время изучения в часах
- prerequisites: какие навыки нужны перед этим (опционально)

ВАЖНО:
- Максимум 3 уровня вложенности
- Логическая последовательность (от простого к сложному)
- Реалистичные оценки времени
- Только технические навыки (Hard Skills)

Верни СТРОГО JSON массив:
[
  {{
    "name": "...",
    "description": "...",
    "level": 1-5,
    "estimated_hours": число,
    "children": [...]
  }}
]
"""

        user_prompt = f"""
Учебный план специальности "{specialty_name}":

{text}

---

Проанализируй и создай иерархию навыков в формате JSON.
"""

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        
        # Извлекаем массив навыков
        if isinstance(result, dict) and "skills" in result:
            return result["skills"]
        elif isinstance(result, list):
            return result
        else:
            return []

    @staticmethod
    async def _create_skills_hierarchy(
        tree_data: List[Dict[str, Any]],
        specialty_id: int,
        source_file: str,
        db: AsyncSession,
        parent_id: int = None
    ) -> int:
        """
        Рекурсивное создание иерархии навыков
        
        Returns: количество созданных навыков
        """
        created_count = 0
        
        for node in tree_data:
            # Создаём навык
            skill = Skill(
                name=node.get("name"),
                description=node.get("description"),
                parent_id=parent_id,
                is_global=False,  # Hard Skill
                specialty_id=specialty_id,
                syllabus_source_file=source_file,
                level=node.get("level", 1),
                estimated_hours=node.get("estimated_hours", 10),
                prerequisites_json=node.get("prerequisites")
            )
            
            db.add(skill)
            await db.flush()  # Получаем ID
            
            created_count += 1
            
            # Рекурсивно обрабатываем детей
            if node.get("children"):
                child_count = await SyllabusParserService._create_skills_hierarchy(
                    node["children"],
                    specialty_id,
                    source_file,
                    db,
                    parent_id=skill.id
                )
                created_count += child_count
        
        return created_count

    @staticmethod
    async def generate_soft_skills(db: AsyncSession) -> int:
        """
        Генерация глобальных Soft Skills
        Вызывается один раз при инициализации системы
        """
        
        soft_skills_data = [
            {
                "name": "Командная работа",
                "description": "Умение эффективно работать в команде",
                "level": 2,
                "estimated_hours": 20,
                "children": [
                    {
                        "name": "Коммуникация",
                        "description": "Чёткое изложение мыслей",
                        "level": 1,
                        "estimated_hours": 10
                    },
                    {
                        "name": "Разрешение конфликтов",
                        "description": "Конструктивное решение споров",
                        "level": 2,
                        "estimated_hours": 10
                    }
                ]
            },
            {
                "name": "Лидерство",
                "description": "Способность вести команду к цели",
                "level": 3,
                "estimated_hours": 30,
                "children": [
                    {
                        "name": "Мотивация команды",
                        "description": "Вдохновлять и поддерживать",
                        "level": 3,
                        "estimated_hours": 15
                    },
                    {
                        "name": "Делегирование",
                        "description": "Распределение задач",
                        "level": 2,
                        "estimated_hours": 15
                    }
                ]
            },
            {
                "name": "Тайм-менеджмент",
                "description": "Эффективное управление временем",
                "level": 2,
                "estimated_hours": 15
            },
            {
                "name": "Критическое мышление",
                "description": "Анализ и оценка информации",
                "level": 3,
                "estimated_hours": 25
            },
            {
                "name": "Адаптивность",
                "description": "Быстрая адаптация к изменениям",
                "level": 2,
                "estimated_hours": 15
            }
        ]
        
        created_count = 0
        
        for skill_data in soft_skills_data:
            # Проверяем, не создан ли уже
            existing = await db.scalar(
                select(Skill).where(
                    Skill.name == skill_data["name"],
                    Skill.is_global == True
                )
            )
            
            if existing:
                continue
            
            skill = Skill(
                name=skill_data["name"],
                description=skill_data["description"],
                is_global=True,
                level=skill_data["level"],
                estimated_hours=skill_data["estimated_hours"]
            )
            
            db.add(skill)
            await db.flush()
            created_count += 1
            
            # Добавляем детей
            if skill_data.get("children"):
                for child_data in skill_data["children"]:
                    child_skill = Skill(
                        name=child_data["name"],
                        description=child_data["description"],
                        parent_id=skill.id,
                        is_global=True,
                        level=child_data["level"],
                        estimated_hours=child_data["estimated_hours"]
                    )
                    db.add(child_skill)
                    created_count += 1
        
        await db.commit()
        return created_count