from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import (
    FeedbackValue,
    Lead,
    LeadFeedback,
    Message,
    MessageProcessingStatus,
    OpportunityStatus,
)
from app.schemas import DashboardRead, PipelineStatusRead

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _count(db: AsyncSession, query) -> int:
    return int((await db.scalar(query)) or 0)


@router.get("", response_model=DashboardRead)
async def dashboard(db: DbSession) -> DashboardRead:
    timezone = ZoneInfo(get_settings().app_timezone)
    local_today = datetime.now(timezone).date()
    day_start = datetime.combine(local_today, time.min, tzinfo=timezone).astimezone(UTC)

    messages_today = await _count(
        db, select(func.count(Message.id)).where(Message.message_date >= day_start)
    )
    prefiltered_today = await _count(
        db,
        select(func.count(Message.id)).where(
            Message.message_date >= day_start, Message.prefilter_result.is_(True)
        ),
    )
    ai_checked_today = await _count(
        db,
        select(func.count(Message.id)).where(
            Message.message_date >= day_start,
            Message.processing_status.in_(
                [MessageProcessingStatus.COMPLETED, MessageProcessingStatus.FAILED]
            ),
        ),
    )
    lead_base = select(func.count(Lead.id)).where(
        Lead.created_at >= day_start, Lead.is_lead.is_(True)
    )
    leads_today = await _count(db, lead_base)
    hot_today = await _count(db, lead_base.where(Lead.lead_score >= 90))
    good_today = await _count(
        db, lead_base.where(Lead.lead_score >= 75, Lead.lead_score < 90)
    )
    possible_today = await _count(
        db, lead_base.where(Lead.lead_score >= 60, Lead.lead_score < 75)
    )
    confirmed_today = await _count(
        db,
        select(func.count(func.distinct(LeadFeedback.lead_id)))
        .join(Lead)
        .where(
            Lead.created_at >= day_start,
            LeadFeedback.feedback == FeedbackValue.POSITIVE,
        ),
    )
    cutoff_30d = datetime.now(UTC) - timedelta(days=30)
    total_leads_30d = await _count(
        db,
        select(func.count(Lead.id)).where(
            Lead.created_at >= cutoff_30d, Lead.is_lead.is_(True)
        ),
    )
    contacts_30d = await _count(
        db,
        select(func.count(Lead.id)).where(
            Lead.created_at >= cutoff_30d,
            Lead.is_lead.is_(True),
            Lead.contact_type == "TELEGRAM_USERNAME",
        ),
    )
    positive_30d = await _count(
        db,
        select(func.count(func.distinct(LeadFeedback.lead_id))).where(
            LeadFeedback.created_at >= cutoff_30d,
            LeadFeedback.feedback == FeedbackValue.POSITIVE,
        ),
    )
    reviewed_30d = await _count(
        db,
        select(func.count(func.distinct(LeadFeedback.lead_id))).where(
            LeadFeedback.created_at >= cutoff_30d
        ),
    )
    contacted_30d = await _count(
        db,
        select(func.count(Lead.id)).where(
            Lead.updated_at >= cutoff_30d,
            Lead.workflow_status.in_(
                [OpportunityStatus.CONTACTED, OpportunityStatus.REPLIED, OpportunityStatus.WON]
            ),
        ),
    )
    won_30d = await _count(
        db,
        select(func.count(Lead.id)).where(
            Lead.updated_at >= cutoff_30d, Lead.workflow_status == OpportunityStatus.WON
        ),
    )
    return DashboardRead(
        messages_today=messages_today,
        prefiltered_today=prefiltered_today,
        ai_checked_today=ai_checked_today,
        leads_today=leads_today,
        hot_today=hot_today,
        good_today=good_today,
        possible_today=possible_today,
        confirmed_today=confirmed_today,
        total_leads_30d=total_leads_30d,
        contact_coverage_30d=round(contacts_30d / total_leads_30d * 100, 1)
        if total_leads_30d
        else 0,
        precision_30d=round(positive_30d / reviewed_30d * 100, 1) if reviewed_30d else 0,
        contacted_30d=contacted_30d,
        won_30d=won_30d,
    )


@router.get("/pipeline", response_model=PipelineStatusRead)
async def pipeline_status(db: DbSession) -> PipelineStatusRead:
    pending = await _count(
        db,
        select(func.count(Message.id)).where(
            Message.processing_status == MessageProcessingStatus.PENDING
        ),
    )
    retrying = await _count(
        db,
        select(func.count(Message.id)).where(
            Message.processing_status == MessageProcessingStatus.RETRY
        ),
    )
    failed = await _count(
        db,
        select(func.count(Message.id)).where(
            Message.processing_status == MessageProcessingStatus.FAILED
        ),
    )
    completed = await _count(
        db,
        select(func.count(Message.id)).where(
            Message.processing_status == MessageProcessingStatus.COMPLETED
        ),
    )
    notifications_pending = await _count(
        db,
        select(func.count(Lead.id)).where(
            Lead.is_lead.is_(True), Lead.notified_at.is_(None)
        ),
    )
    notifications_failed = await _count(
        db,
        select(func.count(Lead.id)).where(Lead.notification_error.is_not(None)),
    )
    return PipelineStatusRead(
        pending=pending,
        retrying=retrying,
        failed=failed,
        completed=completed,
        notifications_pending=notifications_pending,
        notifications_failed=notifications_failed,
    )
