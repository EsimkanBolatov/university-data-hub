import json
import os
import asyncio
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from openai import AsyncOpenAI
import chromadb
from chromadb.config import Settings

from app.core.config import settings
from app.db.models import University, Program

# === НАСТРОЙКИ ===
CHROMA_PATH = "./chroma_db"
EMBEDDING_MODEL = "text-embedding-3-small"

class AIComponents:
    """
    Singleton для клиентов OpenAI и ChromaDB.
    Инициализируется лениво (при первом обращении).
    """
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
            # Инициализация нативного клиента ChromaDB
            cls._chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            
            # Создаем или получаем коллекцию
            cls._collection = cls._chroma_client.get_or_create_collection(
                name="university_data",
                metadata={"hnsw:space": "cosine"} # Используем косинусное сходство
            )
        return cls._collection

class AIService:

    @staticmethod
    def _clean_json_response(text: str) -> Dict:
        """Очищает ответ от Markdown ```json ... ``` и парсит"""
        text = text.strip()
        if text.startswith("```"):
            # Удаляем первую строку (```json) и последнюю (```)
            text = text.split("\n", 1)[-1].rsplit("\n", 1)[0]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw": text}

    @staticmethod
    async def _get_embedding(text: str) -> List[float]:
        """Получает вектор для текста напрямую через OpenAI"""
        client = AIComponents.get_openai()
        # Заменяем переносы строк, чтобы не портить эмбеддинг
        text = text.replace("\n", " ")
        response = await client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return response.data[0].embedding

    @staticmethod
    async def _get_embeddings_batch(texts: List[str]) -> List[List[float]]:
        """Пакетное получение векторов (экономит время)"""
        client = AIComponents.get_openai()
        # OpenAI принимает до 2048 текстов в батче, но лучше слать по 100
        clean_texts = [t.replace("\n", " ") for t in texts]
        response = await client.embeddings.create(input=clean_texts, model=EMBEDDING_MODEL)
        return [item.embedding for item in response.data]

    # ==========================================
    # 1. Синхронизация БД -> Векторы
    # ==========================================
    @staticmethod
    async def sync_database_to_vector_db(db: AsyncSession):
        collection = AIComponents.get_collection()
        
        # 1. Загружаем данные из SQL
        unis = (await db.execute(select(University))).scalars().all()
        progs = (await db.execute(select(Program))).scalars().all()

        ids = []
        documents = []
        metadatas = []

        # Формируем списки для ВУЗов
        for uni in unis:
            text = (
                f"ВУЗ: {uni.name_ru}. Город: {uni.city}. Рейтинг: {uni.rating}. "
                f"Тип: {uni.type}. Описание: {uni.description}. "
                f"Общежитие: {'Есть' if uni.has_dormitory else 'Нет'}."
            )
            ids.append(f"uni_{uni.id}")
            documents.append(text)
            metadatas.append({"type": "university", "db_id": uni.id, "city": uni.city})

        # Формируем списки для Программ
        for prog in progs:
            text = (
                f"Программа: {prog.name_ru}. ВУЗ ID: {prog.university_id}. "
                f"Степень: {prog.degree}. Цена: {prog.price} KZT. "
                f"Предметы: {prog.main_subjects}."
            )
            ids.append(f"prog_{prog.id}")
            documents.append(text)
            metadatas.append({"type": "program", "db_id": prog.id, "uni_id": prog.university_id})

        if not documents:
            return {"status": "empty"}

        # 2. Генерируем векторы (Batching)
        # Разбиваем на пачки по 100 штук, чтобы не словить Timeout
        batch_size = 100
        total_processed = 0
        
        # Удаляем старые данные (для простоты MVP перезаписываем всё)
        try:
            # ChromaDB не имеет delete_all, поэтому удаляем коллекцию и создаем заново
            AIComponents._chroma_client.delete_collection("university_data")
            AIComponents._collection = AIComponents._chroma_client.create_collection("university_data")
            collection = AIComponents._collection
        except:
            pass

        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]

            # Получаем векторы от OpenAI
            embeddings = await AIService._get_embeddings_batch(batch_docs)

            # Сохраняем в Chroma
            collection.add(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_meta
            )
            total_processed += len(batch_docs)

        return {"status": "success", "count": total_processed}

    # ==========================================
    # 2. Чат (RAG)
    # ==========================================
    @staticmethod
    async def chat_rag(question: str):
        client = AIComponents.get_openai()
        collection = AIComponents.get_collection()

        # 1. Векторизуем вопрос
        query_vec = await AIService._get_embedding(question)

        # 2. Ищем похожие документы в Chroma
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=4  # Топ-4 факта
        )
        
        # Извлекаем текст найденных документов
        context_list = results['documents'][0]
        context_str = "\n\n".join(context_list)

        # 3. Формируем промпт
        system_msg = (
            "Ты полезный ассистент University DataHub. "
            "Отвечай на вопросы ТОЛЬКО на основе предоставленного контекста. "
            "Если информации нет, так и скажи. Не выдумывай."
        )
        
        user_msg = f"Контекст:\n{context_str}\n\nВопрос: {question}"

        # 4. Запрос к GPT
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.3
        )

        return response.choices[0].message.content

    # ==========================================
    # 3. Рекомендации (SQL + GPT)
    # ==========================================
    @staticmethod
    async def get_recommendations(user_prefs: dict, db: AsyncSession):
        client = AIComponents.get_openai()

        # 1. SQL Фильтр
        stmt = select(University)
        if user_prefs.get("city"):
            stmt = stmt.where(University.city == user_prefs["city"])
        
        candidates = (await db.execute(stmt.limit(10))).scalars().all()
        
        if not candidates:
            return {"message": "Нет вузов по заданным фильтрам"}

        candidates_text = "\n".join([
            f"- ID {u.id}: {u.name_ru} (Рейтинг: {u.rating}, Описание: {u.description[:150]}...)"
            for u in candidates
        ])

        # 2. Промпт
        system_msg = (
            "Ты эксперт по поступлению. Выбери топ-3 вуза для студента. "
            "Верни ответ строго в JSON формате: "
            '[{"university_id": 1, "reason": "...", "match_score": 95}]'
        )
        
        user_msg = (
            f"Студент: Баллы {user_prefs.get('score')}, Интересы: {user_prefs.get('interests')}, Бюджет: {user_prefs.get('budget')}.\n"
            f"Список кандидатов:\n{candidates_text}"
        )

        # 3. Запрос
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.0
        )

        return AIService._clean_json_response(response.choices[0].message.content)

    # ==========================================
    # 4. Сравнение
    # ==========================================
    @staticmethod
    async def compare_universities(uni_ids: List[int], db: AsyncSession):
        client = AIComponents.get_openai()
        
        stmt = select(University).where(University.id.in_(uni_ids))
        unis = (await db.execute(stmt)).scalars().all()
        
        data_text = "\n".join([
            f"{u.name_ru}: Рейтинг {u.rating}, Студентов {u.total_students}, Общежитие {u.has_dormitory}" 
            for u in unis
        ])

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Сравни университеты и выведи результат в Markdown таблице."},
                {"role": "user", "content": data_text}
            ]
        )
        return response.choices[0].message.content

    # ==========================================
    # 5. Парсинг текста (Админка)
    # ==========================================
    @staticmethod
    async def parse_unstructured_text(text: str):
        client = AIComponents.get_openai()
        
        system_msg = (
            "Извлеки структуру из текста в JSON формате с ключами: "
            "history (str), mission (str), contacts (object). "
            "Если данных нет, ставь null."
        )

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text[:4000]} # Обрезаем, чтобы не превысить токены
            ],
            temperature=0.0
        )
        
        return AIService._clean_json_response(response.choices[0].message.content)