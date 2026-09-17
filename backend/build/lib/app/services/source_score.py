from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeedbackValue, Lead, LeadFeedback, Message, Source


async def calculate_source_stats(db: AsyncSession, source_id: int) -> dict[str, int | float]:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    messages = int(
        (
            await db.scalar(
                select(func.count(Message.id)).where(
                    Message.source_id == source_id, Message.message_date >= cutoff
                )
            )
        )
        or 0
    )
    leads = int(
        (
            await db.scalar(
                select(func.count(Lead.id))
                .join(Message)
                .where(
                    Message.source_id == source_id,
                    Message.message_date >= cutoff,
                    Lead.is_lead.is_(True),
                )
            )
        )
        or 0
    )
    feedback_counts = dict(
        (
            await db.execute(
                select(LeadFeedback.feedback, func.count(LeadFeedback.id))
                .join(Lead)
                .join(Message)
                .where(Message.source_id == source_id, Message.message_date >= cutoff)
                .group_by(LeadFeedback.feedback)
            )
        ).all()
    )
    confirmed = int(feedback_counts.get(FeedbackValue.POSITIVE, 0))
    false_positive = int(feedback_counts.get(FeedbackValue.NEGATIVE, 0))
    reviewed = confirmed + false_positive
    precision = confirmed / reviewed if reviewed else 0.5
    lead_rate = leads / messages if messages else 0
    score = 10 * (
        0.4 * min(lead_rate / 0.02, 1)
        + 0.4 * precision
        + 0.2 * min(leads / 10, 1)
    )
    return {
        "messages_30d": messages,
        "leads_30d": leads,
        "confirmed_30d": confirmed,
        "false_positive_30d": false_positive,
        "source_score": round(score, 1),
    }


async def refresh_source_score(db: AsyncSession, source_id: int) -> float:
    stats = await calculate_source_stats(db, source_id)
    source = await db.get(Source, source_id)
    if source:
        source.source_score = float(stats["source_score"])
    return float(stats["source_score"])
