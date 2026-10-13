import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import AppSettings, DiscoveryQuery, Source, SourceStatus
from app.telegram.manager import TelegramServiceError, telegram_manager

logger = logging.getLogger(__name__)


class DiscoveryWorker:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    async def run(self) -> None:
        logger.info("discovery_worker_started")
        while not self._stop.is_set():
            try:
                await self.process_if_due()
            except Exception:
                logger.exception("discovery_worker_error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=300)
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self._stop.set()

    async def process_if_due(self) -> int:
        if not telegram_manager.connected:
            return 0
        now = datetime.now(UTC)
        async with SessionLocal() as db:
            settings = await db.get(AppSettings, 1)
            if not settings or not settings.automatic_discovery:
                return 0
            cutoff = now - timedelta(hours=settings.discovery_interval_hours)
            queries = list(
                (
                    await db.scalars(
                        select(DiscoveryQuery).where(
                            DiscoveryQuery.enabled.is_(True),
                            or_(
                                DiscoveryQuery.last_run_at.is_(None),
                                DiscoveryQuery.last_run_at <= cutoff,
                            ),
                        )
                    )
                ).all()
            )
            added = 0
            for query in queries:
                try:
                    results = await telegram_manager.search_public_chats(query.query)
                except TelegramServiceError:
                    logger.warning(
                        "automatic_discovery_failed", extra={"query_id": query.id}
                    )
                    continue
                for result in results:
                    exists = await db.scalar(
                        select(Source.id).where(
                            or_(
                                Source.telegram_chat_id == result.telegram_chat_id,
                                Source.username == result.username,
                            )
                        )
                    )
                    if exists:
                        continue
                    try:
                        async with db.begin_nested():
                            db.add(
                                Source(
                                    telegram_chat_id=result.telegram_chat_id,
                                    type=result.source_type,
                                    title=result.title,
                                    username=result.username,
                                    url=f"https://t.me/{result.username}",
                                    is_public=True,
                                    participants_count=result.participants_count,
                                    status=SourceStatus.DISCOVERED,
                                    discovery_source="SCHEDULED_SEARCH",
                                    discovery_query=query.query,
                                )
                            )
                            await db.flush()
                    except IntegrityError:
                        continue
                    added += 1
                query.last_run_at = now
            await db.commit()
            if queries:
                logger.info(
                    "automatic_discovery_completed",
                    extra={"queries": len(queries), "added": added},
                )
            return added
