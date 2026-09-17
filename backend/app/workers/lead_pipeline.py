import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import SessionLocal
from app.lead_detection.classifier import ClassificationError, LeadClassifier, build_classifier
from app.models import Lead, LeadStatus, Message, MessageProcessingStatus, SearchProfile
from app.services.scoring import ScoreFactors, calculate_lead_score
from app.services.source_score import refresh_source_score

logger = logging.getLogger(__name__)
RETRY_DELAYS = (5, 30, 120)


class LeadPipelineWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.classifier: LeadClassifier | None = None
        self.configuration_error: str | None = None
        try:
            self.classifier = build_classifier(settings)
        except ClassificationError:
            self.configuration_error = "AI provider is not configured correctly"
        self._stop = asyncio.Event()

    async def run(self) -> None:
        await self._recover_abandoned_jobs()
        logger.info("lead_pipeline_worker_started", extra={"provider": self.settings.ai_provider})
        while not self._stop.is_set():
            try:
                processed = await self.process_one()
            except Exception:
                logger.exception("lead_pipeline_worker_error")
                processed = False
            if not processed:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1)
                except TimeoutError:
                    pass

    async def stop(self) -> None:
        self._stop.set()
        if self.classifier:
            await self.classifier.close()

    async def process_one(self) -> bool:
        async with SessionLocal() as db:
            message = await self._claim_message(db)
            if message is None:
                return False
            message_id = message.id
            text = message.text
            attempts = message.processing_attempts

        try:
            if not self.classifier:
                raise ClassificationError(self.configuration_error or "AI provider unavailable")
            result = await self.classifier.classify(text)
        except Exception:
            await self._record_failure(message_id, attempts)
            return True

        async with SessionLocal() as db:
            message = await db.get(
                Message,
                message_id,
                options=[selectinload(Message.source), selectinload(Message.lead)],
            )
            if message is None:
                return True
            if message.lead is not None:
                message.processing_status = MessageProcessingStatus.COMPLETED
                await db.commit()
                return True
            profile = (
                await db.get(SearchProfile, message.matched_profile_id)
                if message.matched_profile_id
                else None
            )
            is_lead = result.is_lead
            if profile and profile.categories and result.category.value not in profile.categories:
                is_lead = False
            score = 0
            if is_lead:
                score = calculate_lead_score(
                    ScoreFactors(
                        confidence=result.confidence,
                        intent=result.intent.value,
                        has_specific_task=bool(result.service and result.service != "OTHER"),
                        has_budget=result.budget is not None,
                        has_deadline=result.deadline is not None,
                        urgency=result.urgency.value,
                        source_score=message.source.source_score,
                    )
                )
            lead = Lead(
                search_profile_id=message.matched_profile_id,
                message_id=message.id,
                is_lead=is_lead,
                confidence=result.confidence,
                lead_score=score,
                category=result.category.value,
                service=result.service,
                intent=result.intent.value,
                urgency=result.urgency.value,
                budget=result.budget,
                budget_currency=result.budget_currency,
                deadline=result.deadline,
                summary=result.summary,
                reason=result.reason,
                status=LeadStatus.NEW,
            )
            db.add(lead)
            message.processing_status = MessageProcessingStatus.COMPLETED
            message.processing_error = None
            message.processing_next_attempt_at = None
            await db.flush()
            await refresh_source_score(db, message.source_id)
            await db.commit()
            logger.info(
                "lead_classification_completed",
                extra={"message_id": message.id, "is_lead": is_lead, "score": score},
            )
        return True

    async def _claim_message(self, db: AsyncSession) -> Message | None:
        now = datetime.now(UTC)
        query = (
            select(Message)
            .where(
                Message.prefilter_result.is_(True),
                Message.processing_status.in_(
                    [MessageProcessingStatus.PENDING, MessageProcessingStatus.RETRY]
                ),
                or_(
                    Message.processing_next_attempt_at.is_(None),
                    Message.processing_next_attempt_at <= now,
                ),
                ~Message.lead.has(),
            )
            .order_by(Message.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        message = (await db.scalars(query)).one_or_none()
        if message is None:
            return None
        message.processing_status = MessageProcessingStatus.PROCESSING
        message.processing_attempts += 1
        message.processing_next_attempt_at = None
        await db.commit()
        return message

    async def _record_failure(self, message_id: int, attempts: int) -> None:
        async with SessionLocal() as db:
            message = await db.get(Message, message_id)
            if message is None:
                return
            if attempts <= len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempts - 1]
                message.processing_status = MessageProcessingStatus.RETRY
                message.processing_next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
                error_code = "AI_RETRY_SCHEDULED"
            else:
                message.processing_status = MessageProcessingStatus.FAILED
                message.processing_next_attempt_at = None
                error_code = "AI_PROCESSING_FAILED"
            message.processing_error = error_code
            await db.commit()
            logger.warning(
                "lead_classification_failed",
                extra={"message_id": message_id, "attempt": attempts, "status": error_code},
            )

    async def _recover_abandoned_jobs(self) -> None:
        async with SessionLocal() as db:
            await db.execute(
                update(Message)
                .where(Message.processing_status == MessageProcessingStatus.PROCESSING)
                .values(
                    processing_status=MessageProcessingStatus.RETRY,
                    processing_next_attempt_at=datetime.now(UTC),
                    processing_error="WORKER_RESTARTED",
                )
            )
            await db.commit()
