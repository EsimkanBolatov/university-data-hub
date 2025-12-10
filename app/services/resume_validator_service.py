# app/services/resume_validator_service.py
import json
import re
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import CareerTestSession, CareerTestAnswer
from app.services.ai_service import AIComponents
from app.core.config import settings


class ResumeValidatorService:
    """Сервис для проверки резюме и проведения стресс-интервью"""

    # База знаний по профессиям
    PROFESSION_SKILLS = {
        "Python Backend Developer": {
            "core": ["Python", "FastAPI", "Django", "SQL", "REST API"],
            "advanced": ["AsyncIO", "Docker", "Redis", "PostgreSQL", "Микросервисы"],
            "algorithms": ["Сортировки", "Графы", "Динамическое программирование"]
        },
        "Frontend Developer": {
            "core": ["JavaScript", "React", "HTML", "CSS", "TypeScript"],
            "advanced": ["Next.js", "Redux", "Webpack", "Performance"],
            "algorithms": ["DOM manipulation", "Оптимизация рендера"]
        },
        "Data Analyst": {
            "core": ["Python", "SQL", "Excel", "Pandas", "Visualization"],
            "advanced": ["Machine Learning", "Statistics", "Tableau", "Power BI"],
            "algorithms": ["Regression", "Clustering", "Time Series"]
        }
    }

    @staticmethod
    async def parse_resume(resume_text: str, target_profession: str) -> Dict[str, Any]:
        """
        Парсинг резюме через GPT
        Извлекает: навыки, опыт, образование, сомнительные моменты
        """
        client = AIComponents.get_openai()

        system_prompt = f"""
        Ты эксперт по HR и техническому рекрутингу. 
        Проанализируй резюме кандидата на позицию "{target_profession}".
        
        Задачи:
        1. Извлеки все технические навыки
        2. Определи уровень (junior/middle/senior) по описанию опыта
        3. Найди "подозрительные зоны" (например: "опыт 5 лет, но проектов нет")
        4. Сформируй список навыков для проверки
        
        Верни JSON:
        {{
            "skills": [{{"name": "...", "claimed_level": "...", "years": 0}}],
            "experience_years": 0,
            "education": "...",
            "suspicious_areas": ["причина1", "причина2"],
            "key_projects": ["проект1"],
            "estimated_level": "junior/middle/senior"
        }}
        """

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": resume_text}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        return json.loads(response.choices[0].message.content)

    @staticmethod
    async def generate_interview_questions(
        session_id: int,
        parsed_resume: Dict,
        target_profession: str,
        difficulty: str,
        db: AsyncSession
    ) -> List[Dict]:
        """
        Генерация вопросов для стресс-интервью
        """
        client = AIComponents.get_openai()

        skills_to_check = [s["name"] for s in parsed_resume.get("skills", [])]
        suspicious = parsed_resume.get("suspicious_areas", [])

        prompt = f"""
        Создай 10 технических вопросов для позиции "{target_profession}" ({difficulty}).
        
        Кандидат указал навыки: {', '.join(skills_to_check[:5])}
        Подозрительные зоны: {', '.join(suspicious[:3])}
        
        Требования к вопросам:
        - 5 базовых вопросов (проверка основ)
        - 3 ситуационных (как решил бы задачу)
        - 2 каверзных (проверка глубины знаний)
        - Вопросы должны быть конкретными, без возможности "загуглить" за 30 секунд
        
        Верни JSON:
        {{
            "questions": [
                {{
                    "id": 1,
                    "text": "вопрос",
                    "category": "technical/behavioral/situational",
                    "time_limit": 60,
                    "difficulty": "easy/medium/hard",
                    "expected_keywords": ["ключ1", "ключ2"]
                }}
            ]
        }}
        """

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )

        questions_data = json.loads(response.choices[0].message.content)
        return questions_data["questions"]

    @staticmethod
    async def evaluate_answer(
        question: str,
        answer: str,
        expected_keywords: List[str],
        time_taken: int,
        time_limit: int
    ) -> Dict[str, Any]:
        """
        Оценка ответа через GPT
        """
        client = AIComponents.get_openai()

        # Проверка таймаута
        is_timeout = time_taken > time_limit

        prompt = f"""
        Оцени ответ кандидата на техническом интервью.
        
        Вопрос: {question}
        Ответ: {answer}
        Ожидаемые ключевые слова: {', '.join(expected_keywords)}
        Время: {time_taken}с (лимит: {time_limit}с)
        
        Критерии:
        - Правильность (0-40 баллов)
        - Глубина знаний (0-30 баллов)
        - Структурированность (0-20 баллов)
        - Скорость ответа (0-10 баллов) {'-10 если превысил лимит' if is_timeout else ''}
        
        Верни JSON:
        {{
            "score": 0-100,
            "is_correct": true/false,
            "feedback": "детальный фидбек",
            "strengths": ["что хорошо"],
            "weaknesses": ["что плохо"],
            "confidence_level": "low/medium/high"
        }}
        """

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )

        return json.loads(response.choices[0].message.content)

    @staticmethod
    async def generate_final_verdict(
        session_id: int,
        target_profession: str,
        parsed_resume: Dict,
        interview_results: List[Dict],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Финальный вердикт с roadmap
        """
        client = AIComponents.get_openai()

        # Считаем средний балл
        avg_score = sum(r["score"] for r in interview_results) / len(interview_results) if interview_results else 0
        verified_count = sum(1 for r in interview_results if r["is_correct"])

        resume_skills = parsed_resume.get("skills", [])
        
        prompt = f"""
        Составь финальный отчет для кандидата на позицию "{target_profession}".
        
        Резюме:
        - Заявленные навыки: {json.dumps(resume_skills, ensure_ascii=False)}
        - Опыт: {parsed_resume.get('experience_years', 0)} лет
        
        Интервью:
        - Средний балл: {avg_score:.1f}/100
        - Правильных ответов: {verified_count}/{len(interview_results)}
        - Детали: {json.dumps(interview_results, ensure_ascii=False)[:500]}
        
        Создай:
        1. Индекс готовности (0-100%)
        2. Список подтвержденных навыков
        3. Список неподтвержденных/слабых навыков
        4. Персональную дорожную карту (что учить, в каком порядке)
        5. Рекомендации курсов/книг
        6. Оценку времени до готовности
        
        Верни JSON:
        {{
            "readiness_score": 0-100,
            "verified_skills": [
                {{"name": "...", "level": "confirmed/partial/weak", "evidence": "..."}}
            ],
            "gaps": [
                {{"skill": "...", "priority": "high/medium/low", "reason": "..."}}
            ],
            "roadmap": [
                {{"step": 1, "topic": "...", "resources": ["..."], "duration": "2 недели"}}
            ],
            "recommended_courses": ["курс1", "курс2"],
            "time_to_ready": "примерная оценка",
            "overall_feedback": "итоговый комментарий",
            "next_steps": ["шаг1", "шаг2"]
        }}
        """

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4
        )

        return json.loads(response.choices[0].message.content)

    @staticmethod
    async def start_interview(
        resume_text: str,
        target_profession: str,
        difficulty: str,
        user_id: Optional[int],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Полный процесс: парсинг резюме + генерация вопросов
        """
        # 1. Парсим резюме
        parsed = await ResumeValidatorService.parse_resume(resume_text, target_profession)

        # 2. Создаем сессию
        session = CareerTestSession(
            user_id=user_id,
            difficulty=difficulty,
            total_questions=10,
            current_step=1,
            result_json={"parsed_resume": parsed, "target_profession": target_profession}
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        # 3. Генерируем вопросы
        questions = await ResumeValidatorService.generate_interview_questions(
            session.id, parsed, target_profession, difficulty, db
        )

        # Сохраняем вопросы в сессию
        session.result_json["questions"] = questions
        await db.commit()

        return {
            "session_id": session.id,
            "parsed_resume": parsed,
            "first_question": {
                "question_id": questions[0]["id"],
                "question_text": questions[0]["text"],
                "time_limit_seconds": questions[0]["time_limit"],
                "category": questions[0]["category"]
            },
            "total_questions": len(questions)
        }