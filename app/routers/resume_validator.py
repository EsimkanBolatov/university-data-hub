# app/routers/resume_validator.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db.database import get_db
from app.db.models import User, CareerTestSession, CareerTestAnswer
from app.dependencies import get_current_user
from app.schemas.resume_validator import (
    StartInterviewRequest,
    ResumeUploadResponse,
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    FinalVerdict
)
from app.services.resume_validator_service import ResumeValidatorService

router = APIRouter(prefix="/resume-validator", tags=["Resume Validator"])


@router.post("/start", response_model=ResumeUploadResponse)
async def start_validation_interview(
    request: StartInterviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Начать интервью для проверки навыков
    
    Процесс:
    1. Парсинг резюме (если передано)
    2. Анализ "подозрительных зон"
    3. Генерация вопросов для проверки
    4. Возврат первого вопроса
    """
    if not request.resume_text:
        raise HTTPException(400, "Текст резюме обязателен")

    result = await ResumeValidatorService.start_interview(
        resume_text=request.resume_text,
        target_profession=request.target_profession,
        difficulty=request.difficulty,
        user_id=current_user.id if current_user else None,
        db=db
    )

    return {
        "session_id": result["session_id"],
        "parsed_resume": result["parsed_resume"],
        "suspicious_areas": result["parsed_resume"].get("suspicious_areas", []),
        "target_profession": request.target_profession,
        "difficulty": request.difficulty
    }


@router.post("/answer", response_model=InterviewAnswerResponse)
async def submit_interview_answer(
    request: InterviewAnswerRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Отправить ответ на вопрос интервью
    
    Система:
    - Проверяет правильность ответа
    - Учитывает время ответа
    - Даёт фидбек
    - Возвращает следующий вопрос (или финальный результат)
    """
    # 1. Получаем сессию
    session = await db.get(CareerTestSession, request.session_id)
    if not session or session.is_completed:
        raise HTTPException(404, "Сессия не найдена или завершена")

    # 2. Получаем текущий вопрос
    questions = session.result_json.get("questions", [])
    current_q = next((q for q in questions if q["id"] == request.question_id), None)
    
    if not current_q:
        raise HTTPException(400, "Неверный ID вопроса")

    # 3. Оцениваем ответ
    evaluation = await ResumeValidatorService.evaluate_answer(
        question=current_q["text"],
        answer=request.answer_text,
        expected_keywords=current_q.get("expected_keywords", []),
        time_taken=request.time_taken_seconds,
        time_limit=current_q["time_limit"]
    )

    # 4. Сохраняем ответ
    answer_record = CareerTestAnswer(
        session_id=session.id,
        question_number=session.current_step,
        question_text=current_q["text"],
        answer_text=request.answer_text
    )
    db.add(answer_record)

    # Сохраняем оценку в result_json
    if "interview_results" not in session.result_json:
        session.result_json["interview_results"] = []
    
    session.result_json["interview_results"].append({
        "question_id": request.question_id,
        "score": evaluation["score"],
        "is_correct": evaluation["is_correct"],
        "feedback": evaluation["feedback"],
        "time_taken": request.time_taken_seconds
    })

    # 5. Увеличиваем шаг
    session.current_step += 1

    # 6. Проверяем, закончилось ли интервью
    if session.current_step > len(questions):
        session.is_completed = True
        await db.commit()
        
        # Генерируем финальный вердикт
        verdict = await ResumeValidatorService.generate_final_verdict(
            session_id=session.id,
            target_profession=session.result_json["target_profession"],
            parsed_resume=session.result_json["parsed_resume"],
            interview_results=session.result_json["interview_results"],
            db=db
        )
        
        session.result_json["final_verdict"] = verdict
        await db.commit()

        return {
            "is_correct": evaluation["is_correct"],
            "confidence_score": evaluation["score"],
            "feedback": evaluation["feedback"],
            "next_question": None,
            "is_interview_complete": True
        }

    # 7. Возвращаем следующий вопрос
    await db.commit()
    
    next_q = questions[session.current_step - 1]
    
    return {
        "is_correct": evaluation["is_correct"],
        "confidence_score": evaluation["score"],
        "feedback": evaluation["feedback"],
        "next_question": {
            "question_id": next_q["id"],
            "question_text": next_q["text"],
            "time_limit_seconds": next_q["time_limit"],
            "category": next_q["category"]
        },
        "is_interview_complete": False
    }


@router.get("/verdict/{session_id}", response_model=FinalVerdict)
async def get_final_verdict(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить финальный вердикт после завершения интервью
    
    Содержит:
    - Индекс готовности (0-100%)
    - Верифицированные навыки
    - Неподтвержденные навыки
    - Персональную roadmap
    - Рекомендации курсов
    """
    session = await db.get(CareerTestSession, session_id)
    
    if not session:
        raise HTTPException(404, "Сессия не найдена")
    
    if not session.is_completed:
        raise HTTPException(400, "Интервью еще не завершено")

    verdict = session.result_json.get("final_verdict")
    if not verdict:
        raise HTTPException(500, "Вердикт не был сгенерирован")

    parsed_resume = session.result_json.get("parsed_resume", {})
    
    return {
        "session_id": session.id,
        "readiness_score": verdict["readiness_score"],
        "target_profession": session.result_json["target_profession"],
        "verified_skills": [
            {
                "skill_name": s["name"],
                "claimed_level": s.get("level", "unknown"),
                "verified_level": s.get("level", "unknown"),
                "is_confirmed": s.get("level") == "confirmed",
                "evidence": s.get("evidence", "")
            }
            for s in verdict.get("verified_skills", [])
        ],
        "unverified_skills": [g["skill"] for g in verdict.get("gaps", [])],
        "roadmap": verdict.get("roadmap", []),
        "recommended_courses": verdict.get("recommended_courses", []),
        "estimated_time_to_ready": verdict.get("time_to_ready", "Не определено"),
        "overall_assessment": verdict.get("overall_feedback", "")
    }


@router.get("/history")
async def get_user_validation_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    История прохождения валидаций текущего пользователя
    """
    stmt = (
        select(CareerTestSession)
        .where(CareerTestSession.user_id == current_user.id)
        .where(CareerTestSession.is_completed == True)
        .order_by(CareerTestSession.created_at.desc())
    )
    
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    history = []
    for s in sessions:
        verdict = s.result_json.get("final_verdict", {})
        history.append({
            "session_id": s.id,
            "date": s.created_at.isoformat() if s.created_at else None,
            "profession": s.result_json.get("target_profession", "Неизвестно"),
            "readiness_score": verdict.get("readiness_score", 0),
            "difficulty": s.difficulty
        })

    return {"history": history}