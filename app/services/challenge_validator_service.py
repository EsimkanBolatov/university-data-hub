"""
Сервис проверки челленджей (AI Vision + Manual)
app/services/challenge_validator_service.py
"""
import json
import base64
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.ai_service import AIComponents
from app.core.config import settings
from app.db.models import (
    ChallengeSubmission, 
    EmployerChallenge,
    UserSkillProgress,
    SkillStatus
)


class ChallengeValidatorService:
    """Валидация челленджей через AI Vision или вручную"""

    @staticmethod
    async def validate_submission(
        submission_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Главная функция валидации
        
        Возвращает:
        {
            "status": "checking|approved|rejected",
            "ai_result": {...},
            "needs_manual_review": bool
        }
        """
        
        # 1. Получаем submission
        submission = await db.get(ChallengeSubmission, submission_id)
        if not submission:
            return {"error": "Submission not found"}
        
        # 2. Получаем challenge
        challenge = await db.get(EmployerChallenge, submission.challenge_id)
        if not challenge:
            return {"error": "Challenge not found"}
        
        # 3. Определяем тип проверки
        if challenge.verification_type == "ai_vision":
            result = await ChallengeValidatorService._validate_with_ai_vision(
                submission,
                challenge,
                db
            )
        elif challenge.verification_type == "auto_test":
            result = await ChallengeValidatorService._validate_with_auto_test(
                submission,
                challenge,
                db
            )
        else:  # manual_employer
            result = await ChallengeValidatorService._request_manual_review(
                submission,
                challenge,
                db
            )
        
        await db.commit()
        return result

    @staticmethod
    async def _validate_with_ai_vision(
        submission: ChallengeSubmission,
        challenge: EmployerChallenge,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Проверка через GPT-4 Vision
        
        Пример: проверка чертежа беседки, 3D модели, схемы
        """
        client = AIComponents.get_openai()
        
        # Формируем промпт
        validation_prompt = challenge.ai_validation_prompt or f"""
Проверь, соответствует ли загруженное изображение требованиям задачи:

Задача: {challenge.task_description}

Требования:
{json.dumps(challenge.requirements, ensure_ascii=False, indent=2)}

Оцени по шкале 0-100:
- Соответствие требованиям (40 баллов)
- Качество исполнения (30 баллов)
- Внимание к деталям (20 баллов)
- Креативность (10 баллов)

Верни JSON:
{{
    "approved": true/false,
    "score": 0-100,
    "feedback": "детальный комментарий",
    "criteria_scores": {{"requirement": 40, "quality": 30, ...}},
    "suggestions": ["что улучшить"]
}}
"""

        try:
            # Отправляем изображение в GPT-4 Vision
            # NOTE: submission.submission_file должен быть URL изображения или base64
            
            response = await client.chat.completions.create(
                model="gpt-4o",  # Модель с Vision
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": validation_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": submission.submission_file
                                }
                            }
                        ]
                    }
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            ai_result = json.loads(response.choices[0].message.content)
            
            # Обновляем submission
            submission.ai_check_result = ai_result
            submission.status = "approved" if ai_result.get("approved") else "rejected"
            submission.score = ai_result.get("score")
            submission.feedback = ai_result.get("feedback")
            submission.checked_at = await ChallengeValidatorService._get_current_time()
            
            # Если одобрено - обновляем прогресс
            if ai_result.get("approved"):
                await ChallengeValidatorService._update_user_progress(
                    submission.user_id,
                    challenge.skill_id,
                    submission.submission_file,
                    ai_result.get("score", 100),
                    db
                )
            
            return {
                "status": submission.status,
                "ai_result": ai_result,
                "needs_manual_review": False
            }
            
        except Exception as e:
            submission.status = "error"
            submission.feedback = f"Ошибка AI проверки: {str(e)}"
            
            return {
                "status": "error",
                "error": str(e),
                "needs_manual_review": True
            }

    @staticmethod
    async def _validate_with_auto_test(
        submission: ChallengeSubmission,
        challenge: EmployerChallenge,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Автоматическая проверка кода
        
        Пример: проверка Python кода через тесты
        """
        
        # TODO: Реализация запуска тестов в изолированной среде
        # Можно использовать Docker контейнеры или sandbox API
        
        return {
            "status": "pending",
            "message": "Автоматическая проверка кода ещё не реализована",
            "needs_manual_review": True
        }

    @staticmethod
    async def _request_manual_review(
        submission: ChallengeSubmission,
        challenge: EmployerChallenge,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Запрос ручной проверки работодателем
        """
        
        submission.status = "pending"
        
        # TODO: Отправить уведомление работодателю
        # - Email
        # - WebSocket
        # - Push notification
        
        return {
            "status": "pending",
            "message": "Отправлено на проверку работодателю",
            "employer_id": challenge.employer_id,
            "needs_manual_review": True
        }

    @staticmethod
    async def manual_verify_submission(
        submission_id: int,
        verdict: Dict[str, Any],
        verifier_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Ручная проверка работодателем
        
        verdict = {
            "approved": bool,
            "score": 0-100,
            "feedback": str
        }
        """
        
        submission = await db.get(ChallengeSubmission, submission_id)
        if not submission:
            return {"error": "Submission not found"}
        
        challenge = await db.get(EmployerChallenge, submission.challenge_id)
        
        # Обновляем submission
        submission.manual_check_result = verdict
        submission.status = "approved" if verdict["approved"] else "rejected"
        submission.score = verdict["score"]
        submission.feedback = verdict["feedback"]
        submission.checked_at = await ChallengeValidatorService._get_current_time()
        
        # Обновляем прогресс
        if verdict["approved"]:
            await ChallengeValidatorService._update_user_progress(
                submission.user_id,
                challenge.skill_id,
                submission.submission_file,
                verdict["score"],
                db,
                verified_by=verifier_id
            )
        
        await db.commit()
        
        return {
            "status": submission.status,
            "message": "Проверка завершена"
        }

    @staticmethod
    async def _update_user_progress(
        user_id: int,
        skill_id: int,
        proof_artifact: str,
        score: int,
        db: AsyncSession,
        verified_by: Optional[int] = None
    ):
        """Обновление прогресса студента после успешного челленджа"""
        
        # Ищем или создаём прогресс
        result = await db.execute(
            select(UserSkillProgress).where(
                UserSkillProgress.user_id == user_id,
                UserSkillProgress.skill_id == skill_id
            )
        )
        progress = result.scalar_one_or_none()
        
        if not progress:
            progress = UserSkillProgress(
                user_id=user_id,
                skill_id=skill_id,
                status=SkillStatus.IN_PROGRESS
            )
            db.add(progress)
        
        # Обновляем
        progress.status = SkillStatus.VERIFIED
        progress.progress_percentage = 100
        progress.proof_artifact = proof_artifact
        progress.score = score
        progress.verified_by = verified_by
        progress.completed_at = await ChallengeValidatorService._get_current_time()
        progress.verified_at = await ChallengeValidatorService._get_current_time()

    @staticmethod
    async def _get_current_time() -> str:
        """Текущее время в ISO формате"""
        from datetime import datetime
        return datetime.utcnow().isoformat()


class AIVisionHelper:
    """Вспомогательный класс для работы с изображениями"""
    
    @staticmethod
    def encode_image_to_base64(image_path: str) -> str:
        """Конвертация изображения в base64"""
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    
    @staticmethod
    def create_data_url(base64_image: str, mime_type: str = "image/jpeg") -> str:
        """Создание data URL для GPT-4 Vision"""
        return f"data:{mime_type};base64,{base64_image}"