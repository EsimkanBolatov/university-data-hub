# app/services/ai_rating_service.py
"""
AI-powered университет рейтинг жүйесі
OpenAI арқылы университеттерді бағалау және ұсыныстар беру
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from openai import AsyncOpenAI
import json

from app.core.config import settings
from app.db.models import University, Program, Grant, Dormitory


class AIRatingService:
    """AI-қуатты рейтинг сервисі"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def calculate_ai_rating(
            self,
            university_id: int,
            db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Университет үшін AI рейтингін есептеу
        Критерийлер:
        - Академиялық деңгей (25%)
        - Инфраструктура (20%)
        - Трудоустройство (20%)
        - Халықаралық байланыстар (15%)
        - Студенттік өмір (10%)
        - Қаржылық қолжетімділік (10%)
        """

        # Университет деректерін алу
        uni_query = select(University).where(University.id == university_id)
        uni_result = await db.execute(uni_query)
        uni = uni_result.scalar_one_or_none()

        if not uni:
            return {"error": "Университет табылмады"}

        # Қосымша деректерді жинау
        programs_count = await db.scalar(
            select(func.count(Program.id)).where(Program.university_id == university_id)
        )

        grants_count = await db.scalar(
            select(func.count(Grant.id)).where(Grant.university_id == university_id)
        )

        dormitory_exists = await db.scalar(
            select(func.count(Dormitory.id)).where(Dormitory.university_id == university_id)
        ) > 0

        # Орташа бағдарлама бағасын есептеу
        avg_price = await db.scalar(
            select(func.avg(Program.price)).where(
                Program.university_id == university_id,
                Program.price.isnot(None)
            )
        ) or 0

        # AI промпт құрастыру
        analysis_prompt = self._build_rating_prompt(
            university=uni,
            programs_count=programs_count,
            grants_count=grants_count,
            has_dormitory=dormitory_exists,
            avg_price=avg_price
        )

        # OpenAI-ден талдау алу
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Сіз университеттерді бағалайтын эксперт боламыз. "
                        "Берілген деректерді талдап, әділ рейтинг береміз. "
                        "Жауапты міндетті түрде JSON форматында беріміз."
                    )
                },
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # Жауапты парсинг
        ai_analysis = json.loads(response.choices[0].message.content)

        # Рейтингті дерекқорға жаңарту
        if "overall_rating" in ai_analysis:
            uni.rating = ai_analysis["overall_rating"]
            await db.commit()

        return ai_analysis

    def _build_rating_prompt(
            self,
            university: University,
            programs_count: int,
            grants_count: int,
            has_dormitory: bool,
            avg_price: float
    ) -> str:
        """Рейтинг үшін промпт құрастыру"""

        return f"""
Университетті төмендегі критерийлер бойынша бағалаңыз (0-тен 10-ға дейін):

**УНИВЕРСИТЕТ ТУРАЛЫ АҚПАРАТ:**
- Аты: {university.name_ru}
- Қала: {university.city}
- Түрі: {university.type}
- Құрылған жыл: {university.founded_year or 'Белгісіз'}
- Қазіргі рейтинг: {university.rating}
- Студенттер саны: {university.total_students or 'Ақпарат жоқ'}
- Халықаралық студенттер: {university.international_students or 0}
- Оқытушылар саны: {university.total_teachers or 'Ақпарат жоқ'}
- Докторлар саны: {university.doctors_count or 0}
- PhD иелері: {university.phd_count or 0}
- Кампус ауданы: {university.campus_area or 'Ақпарат жоқ'} га
- Ғимараттар саны: {university.buildings_count or 'Ақпарат жоқ'}

**БАҒДАРЛАМАЛАР:**
- Барлық бағдарламалар: {programs_count}
- Орташа оқу ақысы: {avg_price:,.0f} ₸

**ГРАНТТАР МЕН ҚОЛДАУ:**
- Гранттар саны: {grants_count}

**ИНФРАСТРУКТУРА:**
- Жатақхана: {"Бар" if has_dormitory else "Жоқ"}
- Әскери кафедра: {"Бар" if university.has_military_department else "Жоқ"}

**ТРУДОУСТРОЙСТВО:**
- Трудоустройство деңгейі: {university.employment_rate or 'Ақпарат жоқ'}%

**МИССИЯ:**
{university.mission or 'Көрсетілмеген'}

**СИПАТТАМА:**
{university.description or 'Көрсетілмеген'}

---

**ТАПСЫРМА:** 
Төмендегі JSON форматында жауап беріңіз:

{{
  "overall_rating": <0-10 аралығында жалпы рейтинг>,
  "categories": {{
    "academic_level": <0-10, академиялық деңгей>,
    "infrastructure": <0-10, инфраструктура>,
    "employment": <0-10, жұмысқа орналасу>,
    "international": <0-10, халықаралық байланыстар>,
    "student_life": <0-10, студенттік өмір>,
    "affordability": <0-10, қаржылық қолжетімділік>
  }},
  "strengths": [<3 басты артықшылық>],
  "weaknesses": [<2 жетіспеушілік>],
  "recommendation": "<1 абзацлық ұсыныс>",
  "ideal_for": [<қандай студенттерге сәйкес келеді>]
}}

МАҢЫЗДЫ: Тек қана қол жетімді деректерге сүйеніңіз. Жалған ақпарат қоспаңыз.
"""

    async def compare_universities_ai(
            self,
            university_ids: List[int],
            db: AsyncSession,
            user_preferences: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Университеттерді AI арқылы салыстыру
        user_preferences: {budget, interests, score, city_preference}
        """

        if len(university_ids) < 2:
            return {"error": "Кем дегенде 2 университет керек"}

        if len(university_ids) > 5:
            return {"error": "Максимум 5 университет салыстыруға болады"}

        # Университеттер деректерін жинау
        unis_query = select(University).where(University.id.in_(university_ids))
        unis_result = await db.execute(unis_query)
        universities = unis_result.scalars().all()

        # Әрбір университет үшін толық деректер
        uni_data = []
        for uni in universities:
            programs_count = await db.scalar(
                select(func.count(Program.id)).where(Program.university_id == uni.id)
            )

            avg_price = await db.scalar(
                select(func.avg(Program.price)).where(
                    Program.university_id == uni.id,
                    Program.price.isnot(None)
                )
            ) or 0

            min_price = await db.scalar(
                select(func.min(Program.price)).where(
                    Program.university_id == uni.id,
                    Program.price.isnot(None)
                )
            ) or 0

            uni_data.append({
                "id": uni.id,
                "name": uni.name_ru,
                "city": uni.city,
                "type": uni.type,
                "rating": uni.rating,
                "students": uni.total_students,
                "programs": programs_count,
                "avg_price": avg_price,
                "min_price": min_price,
                "employment": uni.employment_rate,
                "has_dormitory": uni.has_dormitory,
                "description": uni.description
            })

        # Салыстыру промпты
        comparison_prompt = self._build_comparison_prompt(uni_data, user_preferences)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Сіз университеттерді салыстыратын кеңесші боламыз. "
                        "Студенттің қажеттіліктеріне сай ең жақсы нұсқаны табыңыз. "
                        "Жауапты JSON форматында беріңіз."
                    )
                },
                {"role": "user", "content": comparison_prompt}
            ],
            temperature=0.4,
            response_format={"type": "json_object"}
        )

        comparison_result = json.loads(response.choices[0].message.content)

        return comparison_result

    def _build_comparison_prompt(
            self,
            universities: List[Dict],
            user_prefs: Optional[Dict]
    ) -> str:
        """Салыстыру промптын құрастыру"""

        unis_text = "\n\n".join([
            f"""
**{i + 1}. {uni['name']}**
- ID: {uni['id']}
- Қала: {uni['city']}
- Түрі: {uni['type']}
- Рейтинг: {uni['rating']}/10
- Студенттер: {uni['students'] or 'Белгісіз'}
- Бағдарламалар: {uni['programs']}
- Орташа оқу ақысы: {uni['avg_price']:,.0f} ₸
- Минималды оқу ақысы: {uni['min_price']:,.0f} ₸
- Трудоустройство: {uni['employment'] or 'Белгісіз'}%
- Жатақхана: {"Бар" if uni['has_dormitory'] else "Жоқ"}
            """
            for i, uni in enumerate(universities)
        ])

        prefs_text = ""
        if user_prefs:
            prefs_text = f"""
**СТУДЕНТ ҚАЛАУЛАРЫ:**
- Бюджет: {user_prefs.get('budget', 'Көрсетілмеген')}
- Қызығушылықтар: {user_prefs.get('interests', 'Көрсетілмеген')}
- ЕНТ баллдары: {user_prefs.get('score', 'Көрсетілмеген')}
- Қалауы бойынша қала: {user_prefs.get('city_preference', 'Көрсетілмеген')}
            """

        return f"""
Төмендегі университеттерді салыстырып, студент үшін ең жақсы нұсқаны анықтаңыз:

{unis_text}

{prefs_text}

**ТАПСЫРМА:**
JSON форматында жауап беріңіз:

{{
  "recommended_university_id": <ең жақсы нұсқа ID>,
  "ranking": [
    {{"university_id": <id>, "rank": 1, "score": 95, "reason": "себебі"}},
    ...
  ],
  "comparison_table": {{
    "academic": {{"winner_id": <id>, "analysis": "талдау"}},
    "price": {{"winner_id": <id>, "analysis": "талдау"}},
    "infrastructure": {{"winner_id": <id>, "analysis": "талдау"}},
    "location": {{"winner_id": <id>, "analysis": "талдау"}}
  }},
  "final_recommendation": "<толық ұсыныс 2-3 абзац>",
  "alternatives": [
    {{"university_id": <id>, "reason": "неге балама болып табылады"}}
  ]
}}

Студенттің қалауларын ескеріп, объективті талдау жасаңыз.
"""

    async def get_personalized_recommendations(
            self,
            user_profile: Dict[str, Any],
            db: AsyncSession,
            limit: int = 5
    ) -> Dict[str, Any]:
        """
        Жекелендірілген ұсыныстар алу
        user_profile: {
            score: int (ЕНТ баллдары),
            budget: int (бюджет),
            interests: str (қызығушылықтар),
            preferred_city: str (қалауы қала),
            degree: str (bachelor/master/phd),
            need_dormitory: bool
        }
        """

        # Базалық фильтрация
        query = select(University)

        if user_profile.get('preferred_city'):
            query = query.where(University.city == user_profile['preferred_city'])

        if user_profile.get('need_dormitory'):
            query = query.where(University.has_dormitory == True)

        # Топ 15 университетті алу (AI кейінірек түзетеді)
        query = query.order_by(University.rating.desc()).limit(15)

        result = await db.execute(query)
        candidates = result.scalars().all()

        if not candidates:
            return {"error": "Критерийлерге сәйкес университет табылмады"}

        # Әрбір кандидат үшін деректер
        candidates_data = []
        for uni in candidates:
            programs = await db.execute(
                select(Program).where(Program.university_id == uni.id)
            )
            programs_list = programs.scalars().all()

            # Бюджетке сәйкес бағдарламаларды фильтрлеу
            affordable_programs = [
                p for p in programs_list
                if p.price and user_profile.get('budget') and p.price <= user_profile['budget']
            ] if user_profile.get('budget') else programs_list

            candidates_data.append({
                "id": uni.id,
                "name": uni.name_ru,
                "city": uni.city,
                "rating": uni.rating,
                "programs_total": len(programs_list),
                "affordable_programs": len(affordable_programs),
                "has_dormitory": uni.has_dormitory,
                "employment_rate": uni.employment_rate,
                "description": uni.description[:300] if uni.description else ""
            })

        # AI ұсынысын алу
        rec_prompt = self._build_recommendation_prompt(user_profile, candidates_data)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Сіз студенттерге университет таңдауда көмектесетін кеңесші боламыз. "
                        "Олардың профиліне сай ең жақсы 5 нұсқаны ұсыныңыз."
                    )
                },
                {"role": "user", "content": rec_prompt}
            ],
            temperature=0.5,
            response_format={"type": "json_object"}
        )

        recommendations = json.loads(response.choices[0].message.content)

        return recommendations

    def _build_recommendation_prompt(
            self,
            profile: Dict,
            candidates: List[Dict]
    ) -> str:
        """Ұсыныс промптын құрастыру"""

        candidates_text = "\n".join([
            f"{i + 1}. {c['name']} (ID: {c['id']}) - Рейтинг: {c['rating']}, "
            f"Бағдарламалар: {c['programs_total']}, "
            f"Қолжетімді: {c['affordable_programs']}, "
            f"Жатақхана: {'Бар' if c['has_dormitory'] else 'Жоқ'}"
            for i, c in enumerate(candidates)
        ])

        return f"""
**СТУДЕНТ ПРОФИЛІ:**
- ЕНТ баллдары: {profile.get('score', 'Көрсетілмеген')}
- Бюджет: {profile.get('budget', 'Көрсетілмеген')} ₸
- Қызығушылықтар: {profile.get('interests', 'Көрсетілмеген')}
- Қалауы қала: {profile.get('preferred_city', 'Кез келген')}
- Дәреже: {profile.get('degree', 'bachelor')}
- Жатақхана керек: {"Иә" if profile.get('need_dormitory') else "Жоқ"}

**КАНДИДАТТАР:**
{candidates_text}

**ТАПСЫРМА:**
Ең жақсы 5 университетті таңдап, JSON форматында жауап беріңіз:

{{
  "top_recommendations": [
    {{
      "university_id": <id>,
      "match_score": <0-100 үйлесімділік балл>,
      "reasons": [<неге ұсынылады>],
      "pros": [<артықшылықтар>],
      "cons": [<кемшіліктер>],
      "suggested_programs": [<ұсынылатын бағдарламалар>]
    }}
  ],
  "overall_advice": "<жалпы кеңес>",
  "next_steps": [<келесі қадамдар>]
}}

Студенттің мүмкіндіктері мен қызығушылықтарын ескеріңіз.
"""


# API Endpoint үшін жаңа роутер
# app/routers/ai_rating.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional

from app.db.database import get_db
from app.dependencies import get_current_user
from app.db.models import User
from app.services.ai_rating_service import AIRatingService

router = APIRouter(prefix="/ai-rating", tags=["AI Rating"])


class RatingRequest(BaseModel):
    university_id: int


class CompareRequest(BaseModel):
    university_ids: List[int] = Field(..., min_items=2, max_items=5)
    budget: Optional[int] = None
    interests: Optional[str] = None
    score: Optional[int] = None
    city_preference: Optional[str] = None


class RecommendationRequest(BaseModel):
    score: int = Field(..., ge=0, le=140)
    budget: Optional[int] = Field(None, ge=0)
    interests: str
    preferred_city: Optional[str] = None
    degree: str = "bachelor"
    need_dormitory: bool = False


@router.post("/calculate/{university_id}")
async def calculate_university_rating(
        university_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Университет үшін AI рейтингін есептеу
    (Тек админдер үшін)
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Тек админдер рейтинг есептей алады")

    service = AIRatingService()
    result = await service.calculate_ai_rating(university_id, db)

    return result


@router.post("/compare")
async def compare_universities(
        request: CompareRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Университеттерді AI арқылы салыстыру
    """
    service = AIRatingService()

    user_prefs = {
        "budget": request.budget,
        "interests": request.interests,
        "score": request.score,
        "city_preference": request.city_preference
    }

    result = await service.compare_universities_ai(
        request.university_ids,
        db,
        user_prefs
    )

    return result


@router.post("/recommend")
async def get_recommendations(
        request: RecommendationRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Жекелендірілген университет ұсыныстарын алу
    """
    service = AIRatingService()

    result = await service.get_personalized_recommendations(
        user_profile=request.model_dump(),
        db=db
    )

    return result


@router.post("/batch-calculate")
async def batch_calculate_ratings(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Барлық университеттер үшін рейтингті қайта есептеу
    (Тек админдер үшін)
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Қол жетімді емес")

    from app.db.models import University
    from sqlalchemy import select

    unis = await db.execute(select(University))
    all_unis = unis.scalars().all()

    service = AIRatingService()
    results = []

    for uni in all_unis[:10]:  # Алғашқы 10 үшін (demo)
        try:
            result = await service.calculate_ai_rating(uni.id, db)
            results.append({"university_id": uni.id, "status": "success", "rating": result.get("overall_rating")})
        except Exception as e:
            results.append({"university_id": uni.id, "status": "error", "error": str(e)})

    return {"processed": len(results), "results": results}