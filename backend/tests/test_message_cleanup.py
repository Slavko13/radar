from datetime import UTC, datetime, timedelta

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Lead, Message, MessageProcessingStatus, Source
from app.services.message_cleanup import cleanup_old_messages


async def test_cleanup_preserves_useful_leads_recent_and_unfinished_messages() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 10, 22, tzinfo=UTC)
    old = now - timedelta(days=30)
    recent = now - timedelta(days=2)
    async with session_factory() as db:
        source = Source(title="Test source")
        db.add(source)
        await db.flush()

        old_noise = Message(
            source_id=source.id,
            telegram_message_id=1,
            text="noise",
            message_date=old,
            prefilter_result=False,
            processing_status=MessageProcessingStatus.SKIPPED,
        )
        rejected = Message(
            source_id=source.id,
            telegram_message_id=2,
            text="rejected",
            message_date=old,
            prefilter_result=True,
            processing_status=MessageProcessingStatus.COMPLETED,
        )
        useful = Message(
            source_id=source.id,
            telegram_message_id=3,
            text="useful lead",
            message_date=old,
            prefilter_result=True,
            processing_status=MessageProcessingStatus.COMPLETED,
        )
        recent_noise = Message(
            source_id=source.id,
            telegram_message_id=4,
            text="recent noise",
            message_date=recent,
            prefilter_result=False,
            processing_status=MessageProcessingStatus.SKIPPED,
        )
        unfinished = Message(
            source_id=source.id,
            telegram_message_id=5,
            text="unfinished",
            message_date=old,
            prefilter_result=True,
            processing_status=MessageProcessingStatus.PENDING,
        )
        db.add_all([old_noise, rejected, useful, recent_noise, unfinished])
        await db.flush()
        db.add_all(
            [
                Lead(
                    message_id=rejected.id,
                    is_lead=False,
                    confidence=0.2,
                    lead_score=0,
                    offer_type="UNKNOWN",
                    category="OTHER",
                    intent="UNKNOWN",
                    summary="Not a lead",
                ),
                Lead(
                    message_id=useful.id,
                    is_lead=True,
                    confidence=0.9,
                    lead_score=80,
                    offer_type="PROJECT_ORDER",
                    category="WEB_DEVELOPMENT",
                    intent="LOOKING_FOR_CONTRACTOR",
                    summary="Useful lead",
                ),
            ]
        )
        await db.commit()

        result = await cleanup_old_messages(db, retention_days=14, now=now)
        remaining = set(await db.scalars(select(Message.telegram_message_id)))
        remaining_leads = set(await db.scalars(select(Lead.message_id)))

    await engine.dispose()
    assert result.deleted_messages == 2
    assert result.deleted_rejected_leads == 1
    assert remaining == {3, 4, 5}
    assert remaining_leads == {useful.id}
