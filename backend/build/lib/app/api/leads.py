from datetime import UTC, date, datetime, time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.lead_detection.reply_generator import ReplyGenerationError, generate_reply_draft
from app.models import (
    Lead,
    LeadFeedback,
    LeadStatus,
    Message,
    MessageProcessingStatus,
    PortfolioProfile,
)
from app.schemas import (
    DraftResponseRead,
    FeedbackCreate,
    FeedbackRead,
    LeadRead,
    LeadWorkflowUpdate,
    ReprocessLeadsRead,
    ReprocessLeadsRequest,
)
from app.services.source_score import refresh_source_score

router = APIRouter(prefix="/leads", tags=["leads"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def to_read(lead: Lead) -> LeadRead:
    feedback = lead.feedback[-1].feedback if lead.feedback else None
    feedback_reason = lead.feedback[-1].reason if lead.feedback else None
    return LeadRead(
        id=lead.id,
        message_id=lead.message_id,
        source_id=lead.message.source_id,
        source_title=lead.message.source.title,
        message_text=lead.message.text,
        message_url=lead.message.message_url,
        sender_username=lead.message.sender_username,
        sender_name=lead.message.sender_name,
        message_date=lead.message.message_date,
        confidence=lead.confidence,
        lead_score=lead.lead_score,
        title=lead.title,
        offer_type=lead.offer_type,
        category=lead.category,
        service=lead.service,
        requirements=lead.requirements or [],
        work_format=lead.work_format,
        evidence=lead.evidence or [],
        intent=lead.intent,
        urgency=lead.urgency,
        budget=lead.budget,
        budget_currency=lead.budget_currency,
        deadline=lead.deadline,
        summary=lead.summary,
        reason=lead.reason,
        contact_type=lead.contact_type,
        contact_value=lead.contact_value,
        contact_url=lead.contact_url,
        contact_source=lead.contact_source,
        contact_confidence=lead.contact_confidence,
        suggested_materials=lead.suggested_materials or [],
        fit_score=lead.fit_score,
        workflow_status=lead.workflow_status,
        notes=lead.notes,
        feedback_reason=feedback_reason,
        classification_version=lead.classification_version,
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
    offer_type: str | None = None,
    workflow_status: str | None = None,
    has_contact: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[LeadRead]:
    query = lead_query().order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    if min_score is not None:
        query = query.where(Lead.lead_score >= min_score)
    if category:
        query = query.where(Lead.category == category)
    if offer_type:
        query = query.where(Lead.offer_type == offer_type)
    if workflow_status:
        query = query.where(Lead.workflow_status == workflow_status)
    if has_contact is True:
        query = query.where(Lead.contact_type == "TELEGRAM_USERNAME")
    elif has_contact is False:
        query = query.where(Lead.contact_type != "TELEGRAM_USERNAME")
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
    existing = list(
        (
            await db.scalars(
                select(LeadFeedback)
                .where(LeadFeedback.lead_id == lead_id, LeadFeedback.user_id.is_(None))
                .order_by(LeadFeedback.created_at, LeadFeedback.id)
            )
        ).all()
    )
    if existing:
        feedback = existing[-1]
        feedback.feedback = payload.feedback
        feedback.reason = payload.reason
        for duplicate in existing[:-1]:
            await db.delete(duplicate)
    else:
        feedback = LeadFeedback(
            lead_id=lead_id, feedback=payload.feedback, reason=payload.reason
        )
        db.add(feedback)
    lead.status = LeadStatus.REVIEWED
    message = await db.get(Message, lead.message_id)
    if message:
        await db.flush()
        await refresh_source_score(db, message.source_id)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: int, payload: LeadWorkflowUpdate, db: DbSession
) -> LeadRead:
    lead = (await db.scalars(lead_query().where(Lead.id == lead_id))).one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    await db.commit()
    lead = (await db.scalars(lead_query().where(Lead.id == lead_id))).one()
    return to_read(lead)


@router.post("/reprocess", response_model=ReprocessLeadsRead)
async def reprocess_leads(
    payload: ReprocessLeadsRequest, db: DbSession
) -> ReprocessLeadsRead:
    query = (
        select(Lead)
        .options(selectinload(Lead.feedback))
        .order_by(Lead.created_at.desc())
        .limit(payload.limit)
    )
    if payload.only_incomplete:
        query = query.where(
            (Lead.title.is_(None))
            | (Lead.fit_score.is_(None))
            | (Lead.offer_type == "UNKNOWN")
        )
    leads = list((await db.scalars(query)).all())
    queued = 0
    for lead in leads:
        if lead.feedback or lead.workflow_status.value != "NEW":
            continue
        message = await db.get(Message, lead.message_id)
        if not message:
            continue
        await db.delete(lead)
        message.processing_status = MessageProcessingStatus.PENDING
        message.processing_attempts = 0
        message.processing_error = None
        message.processing_next_attempt_at = None
        queued += 1
    await db.commit()
    return ReprocessLeadsRead(queued=queued)


@router.post("/{lead_id}/draft-response", response_model=DraftResponseRead)
async def draft_response(lead_id: int, db: DbSession) -> DraftResponseRead:
    lead = (await db.scalars(lead_query().where(Lead.id == lead_id))).one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    portfolio_profile = await db.get(PortfolioProfile, 1)
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
                "requirements": lead.requirements or [],
                "portfolio_materials": lead.suggested_materials or [],
                "signature": portfolio_profile.contact_signature if portfolio_profile else None,
            },
        )
    except ReplyGenerationError as exc:
        raise HTTPException(502, str(exc)) from exc
    return DraftResponseRead(draft=draft, generated_at=datetime.now(UTC))
