import asyncio
import logging

from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import SessionLocal
from app.models import FeedbackValue, Lead, LeadFeedback, LeadStatus, Message
from app.notifications.bot import BotApiError, TelegramBotClient
from app.services.source_score import refresh_source_score

logger = logging.getLogger(__name__)


class BotFeedbackWorker:
    def __init__(self, settings: Settings, bot: TelegramBotClient) -> None:
        self.settings = settings
        self.bot = bot
        self._stop = asyncio.Event()
        self._offset: int | None = None

    async def run(self) -> None:
        logger.info("bot_feedback_worker_started")
        while not self._stop.is_set():
            if not self.bot.configured:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=2)
                except TimeoutError:
                    pass
                continue
            try:
                updates = await self.bot.get_updates(self._offset)
                for update in updates:
                    try:
                        await self._handle_update(update)
                    except (KeyError, TypeError, ValueError):
                        logger.warning("bot_feedback_update_invalid")
                    finally:
                        if "update_id" in update:
                            self._offset = int(update["update_id"]) + 1
            except BotApiError:
                logger.warning("bot_feedback_poll_failed")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=5)
                except TimeoutError:
                    pass

    async def stop(self) -> None:
        self._stop.set()

    async def _handle_update(self, update: dict) -> None:
        callback = update.get("callback_query")
        if not isinstance(callback, dict):
            return
        callback_id = callback.get("id")
        data = callback.get("data") or ""
        callback_message = callback.get("message") or {}
        callback_chat = callback_message.get("chat") or {}
        chat_id = callback_chat.get("id")
        if str(chat_id) != str(self.settings.telegram_notification_chat_id):
            if callback_id:
                await self.bot.answer_callback(callback_id, "Недоступно")
            return
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "lead" or parts[2] not in {"positive", "negative"}:
            return
        lead_id = int(parts[1])
        feedback_value = (
            FeedbackValue.POSITIVE if parts[2] == "positive" else FeedbackValue.NEGATIVE
        )
        async with SessionLocal() as db:
            lead = await db.get(Lead, lead_id)
            if lead is None:
                answer = "Лид не найден"
            else:
                feedback = LeadFeedback(
                    lead_id=lead_id,
                    feedback=feedback_value,
                    bot_update_id=int(update["update_id"]),
                )
                db.add(feedback)
                lead.status = LeadStatus.REVIEWED
                try:
                    message = await db.get(Message, lead.message_id)
                    await db.flush()
                    if message:
                        await refresh_source_score(db, message.source_id)
                    await db.commit()
                except IntegrityError:
                    await db.rollback()
                answer = "Оценка сохранена"
        if callback_id:
            try:
                await self.bot.answer_callback(callback_id, answer)
            except BotApiError:
                logger.warning("bot_feedback_answer_failed", extra={"lead_id": lead_id})
