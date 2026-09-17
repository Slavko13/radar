from datetime import UTC, date, datetime, time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.lead_detection.reply_generator import ReplyGenerationError, generate_reply_draft
from app.models import Lead, LeadFeedback, LeadStatus, Message
from app.schemas import DraftResponseRead, FeedbackCreate, FeedbackRead, LeadRead
from app.services.source_score import refresh_source_score

router = APIRouter(prefix="/leads", tags=["leads"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def to_read(lead: Lead) -> LeadRead:
    feedback = lead.feedback[-1].feedback if lead.feedback else None
    return LeadRead(
        id=lead.id,
        message_id=lead.message_id,
        source_id=lead.message.source_id,
        source_title=lead.message.source.title,
        message_text=lead.message.text,
        message_url=lead.message.message_url,
        sender_username=lead.message.sender_username,
        message_date=lead.message.message_date,
        confidence=lead.confidence,
        lead_score=lead.lead_score,
        category=lead.category,
        service=lead.service,
        intent=lead.intent,
        urgency=lead.urgency,
        budget=lead.budget,
        budget_currency=lead.budget_currency,
        deadline=lead.deadline,
        summary=lead.summary,
        reason=lead.reason,
        status=lead.status,
        feedback=feedback,
        created_at=lead.created_at,
    )


def lead_query():
    return (
        select(Lead)
        .where(Lead.is_lead.is_(True))
        .options(
            selectinload(Lead.feedback),
            selectinload(Lead.message).selectinload(Message.source),
        )
    )


@router.get("", response_model=list[LeadRead])
async def list_leads(
    db: DbSession,
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    category: str | None = None,
    source_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    band: Literal["HOT", "GOOD", "POSSIBLE"] | None = None,
    feedback: Literal["POSITIVE", "NEGATIVE", "NONE"] | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[LeadRead]:
    query = lead_query().order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    if min_score is not None:
        query = query.where(Lead.lead_score >= min_score)
    if category:
        query = query.where(Lead.category == category)
    if source_id:
        query = query.join(Lead.message).where(Message.source_id == source_id)
    if max_score is not None:
        query = query.where(Lead.lead_score <= max_score)
    if date_from:
        query = query.where(
            Lead.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC)
        )
    if date_to:
        query = query.where(
            Lead.created_at <= datetime.combine(date_to, time.max, tzinfo=UTC)
        )
    if band == "HOT":
        query = query.where(Lead.lead_score >= 90)
    elif band == "GOOD":
        query = query.where(Lead.lead_score >= 75, Lead.lead_score < 90)
    elif band == "POSSIBLE":
        query = query.where(Lead.lead_score >= 60, Lead.lead_score < 75)
    if feedback == "NONE":
        query = query.where(~Lead.feedback.any())
    elif feedback:
        query = query.where(Lead.feedback.any(LeadFeedback.feedback == feedback))
    leads = (await db.scalars(query)).all()
    return [to_read(lead) for lead in leads]


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(lead_id: int, db: DbSession) -> LeadRead:
    lead = (await db.scalars(lead_query().where(Lead.id == lead_id))).one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return to_read(lead)


@router.post(
    "/{lead_id}/feedback",
    response_model=FeedbackRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_feedback(
    lead_id: int, payload: FeedbackCreate, db: DbSession
) -> LeadFeedback:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    feedback = LeadFeedback(lead_id=lead_id, feedback=payload.feedback)
    lead.status = LeadStatus.REVIEWED
    db.add(feedback)
    message = await db.get(Message, lead.message_id)
    if message:
        await db.flush()
        await refresh_source_score(db, message.source_id)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.post("/{lead_id}/draft-response", response_model=DraftResponseRead)
async def draft_response(lead_id: int, db: DbSession) -> DraftResponseRead:
    lead = (await db.scalars(lead_query().where(Lead.id == lead_id))).one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    try:
        draft = await generate_reply_draft(
            get_settings(),
            {
                "message": lead.message.text,
                "summary": lead.summary,
                "category": lead.category,
                "service": lead.service,
                "intent": lead.intent,
                "urgency": lead.urgency,
                "budget": str(lead.budget) if lead.budget is not None else None,
                "deadline": str(lead.deadline) if lead.deadline else None,
            },
        )
    except ReplyGenerationError as exc:
        raise HTTPException(502, str(exc)) from exc
    return DraftResponseRead(draft=draft, generated_at=datetime.now(UTC))
