from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, Message, MessageProcessingStatus


@dataclass(frozen=True)
class CleanupResult:
    deleted_messages: int
    deleted_rejected_leads: int
    retention_days: int
    cutoff: datetime


async def cleanup_old_messages(
    db: AsyncSession, *, retention_days: int, now: datetime | None = None
) -> CleanupResult:
    """Delete old processed noise while preserving every useful lead and unfinished job."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    finished_statuses = (
        MessageProcessingStatus.SKIPPED,
        MessageProcessingStatus.COMPLETED,
    )
    eligible = (
        (Message.message_date < cutoff)
        & Message.processing_status.in_(finished_statuses)
        & ~Message.lead.has(Lead.is_lead.is_(True))
    )
    rejected_leads = int(
        await db.scalar(
            select(func.count(Lead.id))
            .join(Message, Lead.message_id == Message.id)
            .where(
                Message.message_date < cutoff,
                Message.processing_status.in_(finished_statuses),
                Lead.is_lead.is_(False),
            )
        )
        or 0
    )
    result = await db.execute(
        delete(Message).where(eligible).execution_options(synchronize_session=False)
    )
    await db.commit()
    return CleanupResult(
        deleted_messages=int(result.rowcount or 0),
        deleted_rejected_leads=rejected_leads,
        retention_days=retention_days,
        cutoff=cutoff,
    )
