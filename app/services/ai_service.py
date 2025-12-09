# app/services/ai_service.py
import json
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from openai import AsyncOpenAI
import chromadb
from chromadb.config import Settings
import aiohttp

from app.core.config import settings
from app.db.models import University, Program, Grant, Dormitory, Partnership

CHROMA_PATH = "./chroma_db"
EMBEDDING_MODEL = "text-embedding-3-small"


class AIComponents:
    _openai_client = None
    _chroma_client = None
    _collection = None

    @classmethod
    def get_openai(cls):
        if cls._openai_client is None:
            cls._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return cls._openai_client

    @classmethod
    def get_collection(cls):
        if cls._chroma_client is None:
            cls._chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            cls._collection = cls._chroma_client.get_or_create_collection(
                name="university_data",
                metadata={"hnsw:space": "cosine"}
            )
        return cls._collection


class AIService:

    @staticmethod
    async def _web_search(query: str) -> str:
        """Поиск информации в интернете через API"""
        try:
            # Используем DuckDuckGo или другой бесплатный поисковик
            async with aiohttp.ClientSession() as session:
                # Пример с использованием SerpAPI (нужен API ключ) или альтернатива
                url = f"https://html.duckduckgo.com/html/?q={query}+казахстан+университет"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Простое извлечение первых 500 символов
                        return text[:500]
        except Exception as e:
            print(f"Web search error: {e}")
        return ""

    @staticmethod
    def _clean_json_response(text: str) -> Dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("\n", 1)[0]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw": text}

    @staticmethod
    async def _get_embedding(text: str) -> List[float]:
        client = AIComponents.get_openai()
        text = text.replace("\n", " ")
        response = await client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return response.data[0].embedding

    @staticmethod
    async def _get_embeddings_batch(texts: List[str]) -> List[List[float]]:
        client = AIComponents.get_openai()
        clean_texts = [t.replace("\n", " ") for t in texts]
        response = await client.embeddings.create(input=clean_texts, model=EMBEDDING_MODEL)
        return [item.embedding for item in response.data]

    @staticmethod
    async def sync_database_to_vector_db(db: AsyncSession):
        """Синхронизация БД с векторной базой"""
        collection = AIComponents.get_collection()

        # Загружаем все данные
        unis = (await db.execute(select(University))).scalars().all()
        progs = (await db.execute(select(Program))).scalars().all()
        grants = (await db.execute(select(Grant))).scalars().all()
        dorms = (await db.execute(select(Dormitory))).scalars().all()

        ids = []
        documents = []
        metadatas = []

        # Университеты
        for uni in unis:
            text = (
                f"Университет: {uni.name_ru}. "
                f"Город: {uni.city}. "
                f"Рейтинг: {uni.rating}/10. "
                f"Тип: {uni.type}. "
                f"Основан: {uni.founded_year}. "
                f"Студентов: {uni.total_students}. "
                f"Описание: {uni.description or ''}. "
                f"Миссия: {uni.mission or ''}. "
                f"Общежитие: {'Есть' if uni.has_dormitory else 'Нет'}. "
                f"Трудоустройство: {uni.employment_rate}%. "
                f"Адрес: {uni.address or ''}. "
                f"Сайт: {uni.website or ''}"
            )
            ids.append(f"uni_{uni.id}")
            documents.append(text)
            metadatas.append({
                "type": "university",
                "db_id": uni.id,
                "city": uni.city,
                "name": uni.name_ru
            })

        # Программы
        for prog in progs:
            text = (
                f"Программа: {prog.name_ru}. "
                f"Степень: {prog.degree}. "
                f"Цена: {prog.price} KZT в год. "
                f"Длительность: {prog.duration} лет. "
                f"Язык обучения: {prog.language or 'казахский/русский'}. "
                f"Минимальный балл: {prog.min_score}. "
                f"Код: {prog.code or ''}. "
                f"Описание: {prog.description or ''}"
            )
            ids.append(f"prog_{prog.id}")
            documents.append(text)
            metadatas.append({
                "type": "program",
                "db_id": prog.id,
                "uni_id": prog.university_id,
                "degree": prog.degree
            })

        # Гранты
        for grant in grants:
            text = (
                f"Грант: {grant.name}. "
                f"Тип: {grant.type}. "
                f"Описание: {grant.description or ''}. "
                f"Для абитуриентов: {'Да' if grant.available_for_applicants else 'Нет'}. "
                f"Минимальный балл: {grant.min_score_for_grant or 'не указан'}"
            )
            ids.append(f"grant_{grant.id}")
            documents.append(text)
            metadatas.append({
                "type": "grant",
                "db_id": grant.id,
                "uni_id": grant.university_id
            })

        # Общежития
        for dorm in dorms:
            text = (
                f"Общежитие: {dorm.name}. "
                f"Адрес: {dorm.address or ''}. "
                f"Мест: {dorm.capacity}. "
                f"Цена: {dorm.price_per_month} тенге/месяц. "
                f"WiFi: {'Есть' if dorm.has_wifi else 'Нет'}. "
                f"Описание: {dorm.description or ''}"
            )
            ids.append(f"dorm_{dorm.id}")
            documents.append(text)
            metadatas.append({
                "type": "dormitory",
                "db_id": dorm.id,
                "uni_id": dorm.university_id
            })

        if not documents:
            return {"status": "empty", "message": "Нет данных для синхронизации"}

        # Удаляем старую коллекцию
        try:
            AIComponents._chroma_client.delete_collection("university_data")
            AIComponents._collection = AIComponents._chroma_client.create_collection(
                "university_data",
                metadata={"hnsw:space": "cosine"}
            )
            collection = AIComponents._collection
        except:
            pass

        # Батчинг
        batch_size = 100
        total_processed = 0

        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i: i + batch_size]
            batch_ids = ids[i: i + batch_size]
            batch_meta = metadatas[i: i + batch_size]

            embeddings = await AIService._get_embeddings_batch(batch_docs)

            collection.add(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_meta
            )
            total_processed += len(batch_docs)

        return {
            "status": "success",
            "count": total_processed,
            "universities": len(unis),
            "programs": len(progs),
            "grants": len(grants),
            "dormitories": len(dorms)
        }

    @staticmethod
    async def chat_rag(question: str, db: AsyncSession):
        """Чат с поддержкой RAG и веб-поиска"""
        client = AIComponents.get_openai()
        collection = AIComponents.get_collection()

        # 1. Векторный поиск в БД
        query_vec = await AIService._get_embedding(question)
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=5
        )

        context_from_db = "\n\n".join(results['documents'][0]) if results['documents'][0] else ""

        # 2. Если контекста мало, делаем веб-поиск
        web_context = ""
        if len(context_from_db) < 200:
            web_context = await AIService._web_search(question)
            if web_context:
                web_context = f"\n\nДополнительная информация из интернета:\n{web_context}"

        # 3. Формируем промпт
        full_context = context_from_db + web_context

        system_msg = (
            "Ты полезный ассистент University DataHub для университетов Казахстана. "
            "Отвечай на вопросы на основе предоставленного контекста. "
            "Если информации недостаточно, используй данные из интернета и укажи это. "
            "Отвечай на русском языке, чётко и по делу."
        )

        user_msg = f"Контекст:\n{full_context}\n\nВопрос: {question}"

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.4
        )

        answer = response.choices[0].message.content

        # Добавляем источники
        sources = []
        if results.get('metadatas'):
            for meta in results['metadatas'][0][:3]:
                if meta.get('type') == 'university':
                    sources.append(f"Университет ID: {meta['db_id']}")
                elif meta.get('type') == 'program':
                    sources.append(f"Программа ID: {meta['db_id']}")

        return {
            "answer": answer,
            "sources": sources,
            "used_web_search": bool(web_context)
        }

    @staticmethod
    async def get_recommendations(user_prefs: dict, db: AsyncSession):
        """Умные рекомендации с учётом всех параметров"""
        client = AIComponents.get_openai()

        # 1. Фильтруем университеты по базовым критериям
        stmt = select(University)

        if user_prefs.get("city"):
            stmt = stmt.where(University.city.ilike(f"%{user_prefs['city']}%"))

        if user_prefs.get("has_dormitory"):
            stmt = stmt.where(University.has_dormitory == True)

        stmt = stmt.order_by(University.rating.desc()).limit(15)

        candidates = (await db.execute(stmt)).scalars().all()

        if not candidates:
            return {"recommendations": [], "message": "Не найдено университетов по заданным критериям"}

        # 2. Собираем детальную информацию
        uni_details = []
        for uni in candidates:
            # Программы
            prog_query = select(Program).where(Program.university_id == uni.id)
            if user_prefs.get("budget"):
                prog_query = prog_query.where(Program.price <= user_prefs["budget"])

            progs = (await db.execute(prog_query)).scalars().all()

            # Гранты
            grants_count = await db.scalar(
                select(func.count(Grant.id)).where(Grant.university_id == uni.id)
            )

            uni_details.append({
                "id": uni.id,
                "name": uni.name_ru,
                "city": uni.city,
                "rating": uni.rating,
                "type": uni.type,
                "students": uni.total_students,
                "programs_available": len(progs),
                "avg_price": sum(p.price for p in progs if p.price) / len(progs) if progs else 0,
                "min_price": min((p.price for p in progs if p.price), default=0),
                "grants": grants_count,
                "employment_rate": uni.employment_rate,
                "has_dormitory": uni.has_dormitory,
                "description": uni.description[:200] if uni.description else ""
            })

        # 3. AI анализ
        candidates_text = "\n\n".join([
            f"ID {u['id']}: {u['name']}\n"
            f"- Город: {u['city']}\n"
            f"- Рейтинг: {u['rating']}/10\n"
            f"- Доступных программ: {u['programs_available']}\n"
            f"- Минимальная цена: {u['min_price']:,} ₸/год\n"
            f"- Гранты: {u['grants']}\n"
            f"- Трудоустройство: {u['employment_rate']}%\n"
            f"- Общежитие: {'Есть' if u['has_dormitory'] else 'Нет'}"
            for u in uni_details
        ])

        system_msg = (
            "Ты эксперт по поступлению в университеты Казахстана. "
            "Выбери топ-3 лучших варианта для студента. "
            "Верни ответ СТРОГО в JSON формате:\n"
            '{"recommendations": [{"university_id": 1, "match_score": 95, "reason": "...", "pros": ["..."], "cons": ["..."]}]}'
        )

        user_msg = (
            f"Профиль студента:\n"
            f"- Баллы ЕНТ: {user_prefs.get('score', 'не указано')}\n"
            f"- Бюджет: {user_prefs.get('budget', 'не указано')} ₸/год\n"
            f"- Интересы: {user_prefs.get('interests', 'не указано')}\n"
            f"- Город: {user_prefs.get('city', 'любой')}\n\n"
            f"Доступные университеты:\n{candidates_text}"
        )

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        return AIService._clean_json_response(response.choices[0].message.content)

    @staticmethod
    async def compare_universities(uni_ids: List[int], db: AsyncSession):
        """Детальное сравнение университетов"""
        client = AIComponents.get_openai()

        stmt = select(University).where(University.id.in_(uni_ids))
        unis = (await db.execute(stmt)).scalars().all()

        if len(unis) != len(uni_ids):
            return {"error": "Некоторые университеты не найдены"}

        # Собираем полную информацию
        comparison_data = []
        for uni in unis:
            progs_count = await db.scalar(
                select(func.count(Program.id)).where(Program.university_id == uni.id)
            )

            avg_price = await db.scalar(
                select(func.avg(Program.price)).where(
                    Program.university_id == uni.id,
                    Program.price.isnot(None)
                )
            ) or 0

            grants_count = await db.scalar(
                select(func.count(Grant.id)).where(Grant.university_id == uni.id)
            )

            comparison_data.append({
                "id": uni.id,
                "name": uni.name_ru,
                "city": uni.city,
                "type": uni.type,
                "rating": uni.rating,
                "founded": uni.founded_year,
                "students": uni.total_students,
                "teachers": uni.total_teachers,
                "programs": progs_count,
                "avg_price": int(avg_price),
                "grants": grants_count,
                "employment": uni.employment_rate,
                "dormitory": uni.has_dormitory,
                "campus_area": uni.campus_area,
                "description": uni.description
            })

        data_text = "\n\n".join([
            f"{d['name']}:\n"
            f"- Рейтинг: {d['rating']}/10\n"
            f"- Студентов: {d['students']}\n"
            f"- Программ: {d['programs']}\n"
            f"- Средняя цена: {d['avg_price']:,} ₸\n"
            f"- Гранты: {d['grants']}\n"
            f"- Трудоустройство: {d['employment']}%\n"
            f"- Общежитие: {'Есть' if d['dormitory'] else 'Нет'}"
            for d in comparison_data
        ])

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Сравни университеты по ключевым критериям. Выдели победителя в каждой категории."
                },
                {"role": "user", "content": data_text}
            ],
            temperature=0.3
        )

        return {
            "comparison": response.choices[0].message.content,
            "data": comparison_data
        }

    @staticmethod
    async def parse_unstructured_text(text: str):
        """Парсинг неструктурированного текста"""
        client = AIComponents.get_openai()

        system_msg = (
            "Извлеки структуру из текста в JSON формате с ключами: "
            "name, city, founded_year, description, programs, contacts. "
            "Если данных нет, ставь null."
        )

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text[:4000]}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        return AIService._clean_json_response(response.choices[0].message.content)