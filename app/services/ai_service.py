# app/services/ai_service.py
import json
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.docstore.document import Document
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
import os

from app.core.config import settings
from app.db.models import University, Program

# Инициализация OpenAI
llm = ChatOpenAI(
    api_key=settings.OPENAI_API_KEY, 
    model_name=settings.OPENAI_MODEL,
    temperature=0
)

# Инициализация Vector DB (локально)
embeddings = OpenAIEmbeddings(
    api_key=settings.OPENAI_API_KEY,
    model="text-embedding-3-small" # Рекомендуемая модель для эмбеддингов (дешевле и лучше старой davinci)
)

vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

class AIService:
    
    @staticmethod
    async def sync_database_to_vector_db(db: AsyncSession):
        """
        Считывает все университеты и программы из SQL, создает текстовые чанки 
        и сохраняет их в векторную базу для RAG.
        """
        # 1. Получаем данные
        uni_result = await db.execute(select(University))
        universities = uni_result.scalars().all()
        
        prog_result = await db.execute(select(Program))
        programs = prog_result.scalars().all()
        
        documents = []
        
        # 2. Формируем документы для ВУЗов
        for uni in universities:
            content = (
                f"Университет: {uni.name_ru} ({uni.city}). "
                f"Рейтинг: {uni.rating}. Тип: {uni.type}. "
                f"Описание: {uni.description}. Миссия: {uni.mission}. "
                f"Общежитие: {'Есть' if uni.has_dormitory else 'Нет'}. "
                f"Стоимость от {uni.programs[0].price if uni.programs else 'Н/Д'}."
            )
            # Metadata поможет фильтровать поиск
            meta = {"type": "university", "id": uni.id, "city": uni.city}
            documents.append(Document(page_content=content, metadata=meta))
            
        # 3. Формируем документы для Программ
        for prog in programs:
            content = (
                f"Программа: {prog.name_ru}. ВУЗ ID: {prog.university_id}. "
                f"Степень: {prog.degree}. Цена: {prog.price} KZT. "
                f"Предметы: {prog.main_subjects}. Мин. балл: {prog.min_score}."
            )
            meta = {"type": "program", "id": prog.id, "university_id": prog.university_id}
            documents.append(Document(page_content=content, metadata=meta))

        # 4. Обновляем векторную базу
        if documents:
            # Для простоты MVP - удаляем старое и пишем новое (в проде нужен upsert)
            vector_db.delete_collection() 
            vector_db.add_documents(documents)
            return {"status": "success", "count": len(documents)}
        return {"status": "empty"}

    @staticmethod
    async def get_recommendations(user_prefs: dict, db: AsyncSession):
        """
        Гибридная рекомендация: SQL фильтр + AI ранжирование
        """
        # Шаг 1: Грубый фильтр через SQL (по бюджету и городу)
        query = select(University)
        if user_prefs.get("city"):
            query = query.where(University.city == user_prefs["city"])
            
        result = await db.execute(query)
        candidates = result.scalars().all()
        
        # Превращаем кандидатов в краткий текст для AI
        candidates_text = "\n".join([
            f"ID {u.id}: {u.name_ru}, Рейтинг: {u.rating}, Описание: {u.description[:200]}..." 
            for u in candidates
        ])

        # Шаг 2: AI выбирает лучших на основе интересов
        prompt = ChatPromptTemplate.from_template(
            """
            Ты эксперт по поступлению. Пользователь ищет ВУЗ.
            
            Параметры пользователя:
            - Баллы ЕНТ: {score}
            - Интересы: {interests}
            - Бюджет: {budget}
            
            Список доступных кандидатов (прошли фильтр по городу):
            {candidates}
            
            Задание: Выбери ТОП-3 наиболее подходящих ВУЗа из списка.
            Для каждого напиши:
            1. Почему подходит (Match score)
            2. Риски (если баллов мало или дорого)
            
            Ответ верни строго в JSON формате: 
            [{{ "university_id": int, "reason": str, "match_percentage": int }}]
            """
        )
        
        chain = prompt | llm
        response = await chain.ainvoke({
            "score": user_prefs.get("score"),
            "interests": user_prefs.get("interests"),
            "budget": user_prefs.get("budget"),
            "candidates": candidates_text
        })
        
        # Парсим JSON из ответа AI
        try:
            content = response.content.replace("```json", "").replace("```", "")
            return json.loads(content)
        except:
            return {"error": "AI response parsing failed", "raw": response.content}

    @staticmethod
    async def compare_universities(uni_ids: List[int], db: AsyncSession):
        """
        Сравнивает университеты, генерируя аналитический текст
        """
        result = await db.execute(select(University).where(University.id.in_(uni_ids)))
        unis = result.scalars().all()
        
        # Сериализуем данные в JSON для AI
        data_json = json.dumps([{
            "name": u.name_ru, 
            "rating": u.rating, 
            "price_range": "...", # Тут нужно вытащить реальные цены
            "has_dorm": u.has_dormitory,
            "employment": u.employment_rate
        } for u in unis], ensure_ascii=False)

        prompt = ChatPromptTemplate.from_template(
            """
            Сравни следующие университеты для абитуриента:
            {data}
            
            Сделай вывод в виде таблицы (Markdown) и краткого резюме: 
            какой вуз лучше для карьеры, а какой для студенческой жизни.
            """
        )
        
        chain = prompt | llm
        response = await chain.ainvoke({"data": data_json})
        return response.content

    @staticmethod
    async def chat_rag(question: str):
        """
        RAG: Поиск контекста в ChromaDB -> Ответ LLM
        """
        # 1. Поиск похожих кусков в базе
        docs = vector_db.similarity_search(question, k=4)
        context_text = "\n\n".join([d.page_content for d in docs])
        
        # 2. Генерация ответа
        prompt = ChatPromptTemplate.from_template(
            """
            Ты полезный ассистент University DataHub. Отвечай на вопросы только на основе предоставленного контекста.
            Если в контексте нет информации, скажи "К сожалению, у меня нет этой информации в базе".
            Не выдумывай факты. Отвечай на том же языке, на котором задан вопрос (RU/KZ).
            
            Контекст:
            {context}
            
            Вопрос: {question}
            """
        )
        
        chain = prompt | llm
        response = await chain.ainvoke({"context": context_text, "question": question})
        return response.content
        
    @staticmethod
    async def parse_unstructured_text(text: str):
        """
        Для админки: структурирует "сырой" текст в JSON
        """
        prompt = ChatPromptTemplate.from_template(
            """
            Проанализируй текст об университете и извлеки структуру в JSON.
            Поля: "history" (текст), "mission" (текст), "contacts" (объект с phone, email).
            Если данных нет, ставь null.
            
            Текст:
            {text}
            """
        )
        chain = prompt | llm
        response = await chain.ainvoke({"text": text})
        try:
             content = response.content.replace("```json", "").replace("```", "")
             return json.loads(content)
        except:
            return {"error": "Parsing failed"}