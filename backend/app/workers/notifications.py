import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import SessionLocal
from app.models import AppSettings, Lead, Message, SearchProfile
from app.notifications.bot import BotApiError, TelegramBotClient

logger = logging.getLogger(__name__)
NOTIFICATION_RETRY_DELAYS = (5, 30, 120, 300)


class NotificationWorker:
    def __init__(self, settings: Settings, bot: TelegramBotClient) -> None:
        self.settings = settings
        self.bot = bot
        self._stop = asyncio.Event()

    async def run(self) -> None:
        logger.info("notification_worker_started", extra={"configured": self.bot.configured})
        while not self._stop.is_set():
            processed = False
            if self.bot.configured:
                try:
                    processed = await self.process_one()
                except Exception:
                    logger.exception("notification_worker_error")
            if not processed:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=2)
                except TimeoutError:
                    pass

    async def stop(self) -> None:
        self._stop.set()

    async def process_one(self) -> bool:
        now = datetime.now(UTC)
        async with SessionLocal() as db:
            app_settings = await db.get(AppSettings, 1)
            threshold = (
                app_settings.minimum_notification_score
                if app_settings
                else self.settings.lead_score_threshold
            )
            query = (
                select(Lead)
                .outerjoin(SearchProfile, Lead.search_profile_id == SearchProfile.id)
                .where(
                    Lead.is_lead.is_(True),
                    Lead.notified_at.is_(None),
                    or_(
                        and_(
                            Lead.search_profile_id.is_(None),
                            Lead.lead_score >= threshold,
                        ),
                        and_(
                            Lead.search_profile_id.is_not(None),
                            SearchProfile.enabled.is_(True),
                            SearchProfile.notification_enabled.is_(True),
                            Lead.lead_score >= SearchProfile.min_score,
                        ),
                    ),
                    or_(
                        Lead.notification_next_attempt_at.is_(None),
                        Lead.notification_next_attempt_at <= now,
                    ),
                )
                .options(selectinload(Lead.message).selectinload(Message.source))
                .order_by(Lead.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            lead = (await db.scalars(query)).one_or_none()
            if lead is None:
                return False
            lead.notification_attempts += 1
            lead.notification_next_attempt_at = now + timedelta(minutes=5)
            await db.commit()
            lead_id = lead.id

        try:
            await self.bot.send_lead(lead)
        except BotApiError:
            await self._record_failure(lead_id)
            return True

        async with SessionLocal() as db:
            lead = await db.get(Lead, lead_id)
            if lead:
                lead.notified_at = datetime.now(UTC)
                lead.notification_next_attempt_at = None
                lead.notification_error = None
                await db.commit()
        logger.info("lead_notification_sent", extra={"lead_id": lead_id})
        return True

    async def _record_failure(self, lead_id: int) -> None:
        async with SessionLocal() as db:
            lead = await db.get(Lead, lead_id)
            if lead is None:
                return
            index = min(max(lead.notification_attempts - 1, 0), len(NOTIFICATION_RETRY_DELAYS) - 1)
            delay = NOTIFICATION_RETRY_DELAYS[index]
            lead.notification_next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
            lead.notification_error = "BOT_NOTIFICATION_FAILED"
            await db.commit()
        logger.warning(
            "lead_notification_failed",
            extra={"lead_id": lead_id, "attempt": lead.notification_attempts},
        )
