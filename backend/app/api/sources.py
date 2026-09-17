from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Source, SourceStatus
from app.schemas import (
    SourceAnalysisRead,
    SourceAnalysisRequest,
    SourceCreate,
    SourceRead,
    SourceStatsRead,
    SourceUpdate,
    TelegramDialogImport,
    TelegramDialogRead,
)
from app.services.source_score import calculate_source_stats, refresh_source_score
from app.telegram.links import parse_telegram_target
from app.telegram.manager import TelegramServiceError, telegram_manager

router = APIRouter(prefix="/sources", tags=["sources"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[SourceRead])
async def list_sources(db: DbSession) -> list[Source]:
    return list((await db.scalars(select(Source).order_by(Source.created_at.desc()))).all())


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceCreate, db: DbSession) -> Source:
    raw_target = payload.url or payload.username or ""
    try:
        target = parse_telegram_target(raw_target)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    username = target.username
    is_invite = target.invite_hash is not None
    source = Source(
        title=payload.title or (f"@{username}" if username else "Private Telegram chat"),
        username=username,
        url=payload.url,
        invite_url=payload.url if is_invite else None,
        is_public=not is_invite,
        status=SourceStatus.REVIEW,
    )
    db.add(source)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Source already exists") from exc
    await db.refresh(source)
    return source


@router.post("/{source_id}/join", response_model=SourceRead)
async def join_source(source_id: int, db: DbSession) -> Source:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    try:
        result = await telegram_manager.join_source(source)
    except TelegramServiceError as exc:
        if exc.code in {"INVALID_INVITE", "UNAVAILABLE"}:
            source.status = SourceStatus.UNAVAILABLE
            await db.commit()
        http_status = 429 if exc.code == "FLOOD_WAIT" else 409
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(
            http_status,
            {"code": exc.code, "message": str(exc), "retry_after": exc.retry_after},
            headers=headers,
        ) from exc
    source.status = result.status
    if result.telegram_chat_id is not None:
        source.telegram_chat_id = result.telegram_chat_id
    if result.title:
        source.title = result.title
    if result.username:
        source.username = result.username.lower()
    if result.participants_count is not None:
        source.participants_count = result.participants_count
    if result.source_type:
        source.type = result.source_type
    if result.status == SourceStatus.ACTIVE:
        source.joined_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/{source_id}/stats", response_model=SourceStatsRead)
async def source_stats(source_id: int, db: DbSession) -> SourceStatsRead:
    if not await db.get(Source, source_id):
        raise HTTPException(404, "Source not found")
    stats = await calculate_source_stats(db, source_id)
    return SourceStatsRead(**stats)


@router.post("/{source_id}/analyze", response_model=SourceAnalysisRead)
async def analyze_source(
    source_id: int, payload: SourceAnalysisRequest, db: DbSession
) -> SourceAnalysisRead:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    if source.status not in {SourceStatus.ACTIVE, SourceStatus.PAUSED}:
        raise HTTPException(409, "Join the source before analysis")
    try:
        result = await telegram_manager.backfill_source(source, limit=payload.limit)
    except TelegramServiceError as exc:
        status_code = 429 if exc.code == "FLOOD_WAIT" else 409
        raise HTTPException(
            status_code,
            {"code": exc.code, "message": str(exc), "retry_after": exc.retry_after},
        ) from exc
    score = await refresh_source_score(db, source_id)
    await db.commit()
    return SourceAnalysisRead(
        fetched=result.fetched,
        inserted=result.inserted,
        candidates=result.candidates,
        source_score=score,
    )


@router.get("/telegram-dialogs", response_model=list[TelegramDialogRead])
async def telegram_dialogs(db: DbSession) -> list[TelegramDialogRead]:
    try:
        dialogs = await telegram_manager.list_joined_chats()
    except TelegramServiceError as exc:
        status_code = 429 if exc.code == "FLOOD_WAIT" else 409
        raise HTTPException(
            status_code,
            {"code": exc.code, "message": str(exc), "retry_after": exc.retry_after},
        ) from exc
    sources = list((await db.scalars(select(Source))).all())
    by_chat_id = {
        source.telegram_chat_id: source for source in sources if source.telegram_chat_id
    }
    by_username = {source.username: source for source in sources if source.username}
    result: list[TelegramDialogRead] = []
    for dialog in dialogs:
        source = by_chat_id.get(dialog.telegram_chat_id)
        if source is None and dialog.username:
            source = by_username.get(dialog.username)
        result.append(
            TelegramDialogRead(
                **dialog.__dict__,
                source_id=source.id if source else None,
                source_status=source.status if source else None,
                already_added=bool(source and source.status != SourceStatus.DISCOVERED),
            )
        )
    return result


@router.post("/import-dialog", response_model=SourceRead)
async def import_telegram_dialog(
    payload: TelegramDialogImport, db: DbSession
) -> Source:
    try:
        dialog = await telegram_manager.get_joined_chat(payload.telegram_chat_id)
    except TelegramServiceError as exc:
        status_code = 429 if exc.code == "FLOOD_WAIT" else 409
        raise HTTPException(
            status_code,
            {"code": exc.code, "message": str(exc), "retry_after": exc.retry_after},
        ) from exc
    conditions = [Source.telegram_chat_id == dialog.telegram_chat_id]
    if dialog.username:
        conditions.append(Source.username == dialog.username)
    source = (await db.scalars(select(Source).where(or_(*conditions)))).one_or_none()
    if source is None:
        source = Source(telegram_chat_id=dialog.telegram_chat_id, title=dialog.title)
        db.add(source)
    source.telegram_chat_id = dialog.telegram_chat_id
    source.title = dialog.title
    source.username = dialog.username
    source.url = f"https://t.me/{dialog.username}" if dialog.username else None
    source.is_public = dialog.username is not None
    source.type = dialog.source_type
    source.participants_count = dialog.participants_count
    source.status = SourceStatus.ACTIVE
    source.discovery_source = "ACCOUNT_DIALOGS"
    source.joined_at = datetime.now(UTC)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Telegram chat is already present") from exc
    await db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(source_id: int, db: DbSession) -> Source:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return source


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: int, payload: SourceUpdate, db: DbSession
) -> Source:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    await db.commit()
    await db.refresh(source)
    return source


@router.post("/{source_id}/activate", response_model=SourceRead)
async def activate_source(source_id: int, db: DbSession) -> Source:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    if source.telegram_chat_id is None:
        raise HTTPException(409, "Join and resolve the Telegram source before activation")
    return await update_source(source_id, SourceUpdate(status=SourceStatus.ACTIVE), db)


@router.post("/{source_id}/pause", response_model=SourceRead)
async def pause_source(source_id: int, db: DbSession) -> Source:
    return await update_source(source_id, SourceUpdate(status=SourceStatus.PAUSED), db)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: int, db: DbSession) -> None:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    await db.delete(source)
    await db.commit()
