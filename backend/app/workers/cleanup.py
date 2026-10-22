import asyncio
import logging

from app.database import SessionLocal
from app.models import AppSettings
from app.services.message_cleanup import CleanupResult, cleanup_old_messages

logger = logging.getLogger(__name__)
DEFAULT_RETENTION_DAYS = 14
CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60


class MessageCleanupWorker:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._cleanup_lock = asyncio.Lock()

    async def run(self) -> None:
        logger.info("message_cleanup_worker_started")
        while not self._stop.is_set():
            try:
                await self.cleanup_now()
            except Exception:
                logger.exception("message_cleanup_failed")
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=CLEANUP_INTERVAL_SECONDS
                )
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self._stop.set()

    async def cleanup_now(self) -> CleanupResult:
        async with self._cleanup_lock, SessionLocal() as db:
            settings = await db.get(AppSettings, 1)
            retention_days = (
                settings.message_retention_days if settings else DEFAULT_RETENTION_DAYS
            )
            result = await cleanup_old_messages(db, retention_days=retention_days)
            logger.info(
                "message_cleanup_completed",
                extra={
                    "deleted_messages": result.deleted_messages,
                    "deleted_rejected_leads": result.deleted_rejected_leads,
                    "retention_days": result.retention_days,
                },
            )
            return result
