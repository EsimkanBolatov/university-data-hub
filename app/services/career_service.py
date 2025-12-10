# app/services/career_service.py
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.db.models import CareerTestSession, CareerTestAnswer, University, Program
from app.services.ai_service import AIComponents
from app.core.config import settings

class CareerService:
    # 5 Стандартных вопросов для начала
    STANDARD_QUESTIONS = [
        "Какие школьные предметы вам даются легче всего и вызывают наибольший интерес?",
        "Чем вы любите заниматься в свободное время (хобби, увлечения)?",
        "Представьте идеальный рабочий день через 10 лет. Где вы и что делаете?",
        "Что для вас важнее: высокая зарплата, творческая реализация или помощь людям?",
        "Какие ваши сильные стороны отмечают окружающие (родители, друзья, учителя)?"
    ]

    @staticmethod
    async def start_test(user_id: int | None, difficulty: str, count: int, db: AsyncSession):
        """Начало теста"""
        session = CareerTestSession(
            user_id=user_id,
            difficulty=difficulty,
            total_questions=count,
            current_step=1
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        return {
            "session_id": session.id,
            "current_step": 1,
            "total_steps": count,
            "question": CareerService.STANDARD_QUESTIONS[0],
            "is_finished": False
        }

    @staticmethod
    async def process_answer(session_id: int, answer_text: str, db: AsyncSession):
        """Обработка ответа и генерация следующего шага"""
        # 1. Получаем сессию
        session = await db.get(CareerTestSession, session_id)
        if not session or session.is_completed:
            return None

        # 2. Сохраняем ответ
        # Сначала нужно понять, какой был вопрос.
        # Если шаг <= 5, берем из списка. Если > 5, он должен был быть сгенерирован ранее (но мы упростим и восстановим контекст)
        
        prev_question = ""
        if session.current_step <= 5:
            prev_question = CareerService.STANDARD_QUESTIONS[session.current_step - 1]
        else:
            # Для шагов > 5 вопрос должен был быть передан на фронт, 
            # здесь мы предполагаем, что фронт ответил на последний сгенерированный вопрос.
            # В реальной системе можно хранить "текущий вопрос" в БД, но пока опустим.
            pass 

        # Сохраняем в историю
        new_answer = CareerTestAnswer(
            session_id=session.id,
            question_number=session.current_step,
            question_text=prev_question or "AI Question", # Упрощение
            answer_text=answer_text
        )
        db.add(new_answer)
        
        # Обновляем шаг
        session.current_step += 1
        await db.commit()

        # 3. Проверяем, конец ли теста
        if session.current_step > session.total_questions:
            session.is_completed = True
            await db.commit()
            return await CareerService._generate_results(session, db)

        # 4. Генерируем следующий вопрос
        next_question = ""
        if session.current_step <= 5:
            next_question = CareerService.STANDARD_QUESTIONS[session.current_step - 1]
        else:
            # Генерируем AI вопрос на основе истории
            next_question = await CareerService._generate_ai_question(session, db)
            # Тут можно обновить last_answer с правильным текстом вопроса, если нужно точность

        return {
            "session_id": session.id,
            "current_step": session.current_step,
            "total_steps": session.total_questions,
            "question": next_question,
            "is_finished": False
        }

    @staticmethod
    async def _generate_ai_question(session: CareerTestSession, db: AsyncSession) -> str:
        """Генерация адаптивного вопроса через GPT"""
        # Загружаем историю
        history = await db.execute(
            select(CareerTestAnswer)
            .where(CareerTestAnswer.session_id == session.id)
            .order_by(CareerTestAnswer.question_number)
        )
        answers = history.scalars().all()
        
        conversation_text = "\n".join([f"Q: {a.question_text}\nA: {a.answer_text}" for a in answers])
        
        client = AIComponents.get_openai()
        
        prompt = f"""
        Ты профессиональный профориентолог. Школьник проходит тест.
        Уровень сложности вопросов: {session.difficulty}.
        
        История ответов школьника:
        {conversation_text}
        
        Задача: На основе ответов придумай ОДИН следующий вопрос, чтобы глубже понять, какая профессия ему подходит.
        Вопрос должен быть уточняющим, не повторяться и помогать сузить круг профессий.
        """

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
        
        return response.choices[0].message.content

    @staticmethod
    async def _generate_results(session: CareerTestSession, db: AsyncSession):
        """Финал: анализ ответов и подбор ВУЗов"""
        # Загружаем историю
        history = await db.execute(
            select(CareerTestAnswer)
            .where(CareerTestAnswer.session_id == session.id)
            .order_by(CareerTestAnswer.question_number)
        )
        answers = history.scalars().all()
        conversation_text = "\n".join([f"Q: {a.question_text}\nA: {a.answer_text}" for a in answers])

        client = AIComponents.get_openai()

        # Промпт для анализа
        prompt = f"""
        Проанализируй ответы школьника на профориентационный тест.
        
        История:
        {conversation_text}
        
        Задача:
        1. Составь краткий психологический портрет и анализ навыков.
        2. Предложи топ-3 профессии, которые идеально подходят.
        3. Для каждой профессии укажи ключевые слова для поиска программ в базе данных (на русском).
        
        Верни ответ СТРОГО в JSON формате:
        {{
            "analysis": "текст анализа...",
            "professions": [
                {{"name": "Профессия 1", "reason": "почему подходит", "keywords": ["ключевое1", "ключевое2"]}},
                ...
            ]
        }}
        """

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        ai_result = json.loads(response.choices[0].message.content)
        
        # Поиск университетов по ключевым словам
        recommended_universities = {} # Используем dict чтобы убрать дубликаты по ID
        
        all_keywords = []
        for prof in ai_result["professions"]:
            all_keywords.extend(prof["keywords"])
            
        # Ищем программы, содержащие ключевые слова
        # Это упрощенный поиск. В идеале использовать векторный поиск (как в ai_service.py)
        if all_keywords:
            filters = [Program.name_ru.ilike(f"%{kw}%") for kw in all_keywords[:5]] # Берем первые 5 для скорости
            stmt = (
                select(University)
                .join(Program)
                .where(or_(*filters))
                .options(selectinload(University.programs)) # Подгружаем программы
                .limit(5)
            )
            
            result = await db.execute(stmt)
            unis = result.scalars().all()
            
            for u in unis:
                # Превращаем модель SQLAlchemy в Pydantic схему (упрощенно)
                recommended_universities[u.id] = {
                    "id": u.id,
                    "name_ru": u.name_ru,
                    "city": u.city,
                    "rating": u.rating,
                    "logo_url": u.logo_url,
                    "has_dormitory": u.has_dormitory,
                    "programs_count": len(u.programs),
                    "type": u.type
                }

        return {
            "session_id": session.id,
            "is_finished": True,
            "analysis": ai_result["analysis"],
            "suggested_professions": ai_result["professions"],
            "recommended_universities": list(recommended_universities.values())
        }