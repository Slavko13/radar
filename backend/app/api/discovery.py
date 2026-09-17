from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DiscoveryQuery, Source, SourceStatus
from app.schemas import (
    DiscoveryQueryCreate,
    DiscoveryQueryRead,
    DiscoveryQueryUpdate,
    DiscoveryRunRead,
    SourceRead,
)
from app.telegram.manager import TelegramServiceError, telegram_manager

router = APIRouter(prefix="/discovery", tags=["discovery"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/queries", response_model=list[DiscoveryQueryRead])
async def list_queries(db: DbSession) -> list[DiscoveryQuery]:
    return list((await db.scalars(select(DiscoveryQuery).order_by(DiscoveryQuery.query))).all())


@router.post(
    "/queries", response_model=DiscoveryQueryRead, status_code=status.HTTP_201_CREATED
)
async def create_query(payload: DiscoveryQueryCreate, db: DbSession) -> DiscoveryQuery:
    query = DiscoveryQuery(query=payload.query.strip(), enabled=payload.enabled)
    db.add(query)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Discovery query already exists") from exc
    await db.refresh(query)
    return query


@router.patch("/queries/{query_id}", response_model=DiscoveryQueryRead)
async def update_query(
    query_id: int, payload: DiscoveryQueryUpdate, db: DbSession
) -> DiscoveryQuery:
    query = await db.get(DiscoveryQuery, query_id)
    if not query:
        raise HTTPException(404, "Discovery query not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(query, key, value.strip() if key == "query" and value else value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Discovery query already exists") from exc
    await db.refresh(query)
    return query


@router.delete("/queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(query_id: int, db: DbSession) -> None:
    query = await db.get(DiscoveryQuery, query_id)
    if not query:
        raise HTTPException(404, "Discovery query not found")
    await db.delete(query)
    await db.commit()


@router.get("/results", response_model=list[SourceRead])
async def discovery_results(db: DbSession) -> list[Source]:
    return list(
        (
            await db.scalars(
                select(Source)
                .where(Source.status.in_([SourceStatus.DISCOVERED, SourceStatus.REVIEW]))
                .order_by(Source.created_at.desc())
            )
        ).all()
    )


@router.delete("/results", status_code=status.HTTP_204_NO_CONTENT)
async def clear_discovery_results(db: DbSession) -> None:
    await db.execute(delete(Source).where(Source.status == SourceStatus.DISCOVERED))
    await db.commit()


@router.post("/run", response_model=DiscoveryRunRead)
async def run_discovery(db: DbSession) -> DiscoveryRunRead:
    queries = (
        await db.scalars(select(DiscoveryQuery).where(DiscoveryQuery.enabled.is_(True)))
    ).all()
    if not queries:
        raise HTTPException(409, "No enabled discovery queries")
    found = 0
    added = 0
    for query in queries:
        try:
            results = await telegram_manager.search_public_chats(query.query)
        except TelegramServiceError as exc:
            status_code = 429 if exc.code == "FLOOD_WAIT" else 409
            raise HTTPException(
                status_code,
                {"code": exc.code, "message": str(exc), "retry_after": exc.retry_after},
            ) from exc
        found += len(results)
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
                            discovery_source="TELEGRAM_SEARCH",
                            discovery_query=query.query,
                        )
                    )
                    await db.flush()
            except IntegrityError:
                continue
            else:
                added += 1
        query.last_run_at = datetime.now(UTC)
        await db.commit()
    return DiscoveryRunRead(queries_run=len(queries), found=found, added=added)
