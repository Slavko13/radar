from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.lead_detection.classifier import ClassificationError
from app.models import AppSettings
from app.notifications.bot import BotApiError, TelegramBotClient
from app.schemas import (
    AiConfigureRequest,
    AiStatusRead,
    IntegrationStatusRead,
    MessageCleanupRead,
    NotificationBotChatRead,
    NotificationBotConfigureRequest,
    NotificationBotProbeRead,
    NotificationBotProbeRequest,
    NotificationBotStatusRead,
    SettingsRead,
    SettingsUpdate,
)

router = APIRouter(prefix="/settings", tags=["settings"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/integrations", response_model=IntegrationStatusRead)
async def integration_status(request: Request) -> IntegrationStatusRead:
    config = request.app.state.workers.settings
    bot = _bot(request)
    return IntegrationStatusRead(
        ai_configured=config.ai_configured,
        ai_provider=config.ai_provider,
        ai_model=config.ai_model,
        notification_bot_configured=bot.configured,
    )


@router.get("/ai", response_model=AiStatusRead)
async def ai_status(request: Request) -> AiStatusRead:
    config = request.app.state.workers.settings
    return AiStatusRead(
        configured=config.ai_configured,
        provider=config.ai_provider,
        model=config.ai_model,
        base_url=config.ai_base_url if config.ai_provider != "mock" else None,
    )


@router.post("/ai", response_model=AiStatusRead)
async def configure_ai(payload: AiConfigureRequest, request: Request) -> AiStatusRead:
    try:
        await request.app.state.workers.configure_ai(
            payload.provider,
            payload.api_key.strip(),
            payload.model.strip(),
            payload.base_url.strip().rstrip("/"),
        )
    except ClassificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-провайдер не принял ключ, модель или формат structured output",
        ) from exc
    return await ai_status(request)


@router.delete("/ai", response_model=AiStatusRead)
async def disconnect_ai(request: Request) -> AiStatusRead:
    await request.app.state.workers.use_mock_ai()
    return await ai_status(request)


def _bot(request: Request) -> TelegramBotClient:
    return request.app.state.workers.bot


def _bot_error(exc: BotApiError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Telegram не принял токен или не разрешил боту отправлять сообщения в этот чат",
    )


@router.get("/notification-bot", response_model=NotificationBotStatusRead)
async def notification_bot_status(request: Request) -> NotificationBotStatusRead:
    bot = _bot(request)
    if not bot.configured:
        return NotificationBotStatusRead(configured=False)
    try:
        description = await bot.describe()
    except BotApiError:
        return NotificationBotStatusRead(
            configured=True, chat_id=str(bot.chat_id) if bot.chat_id else None
        )
    return NotificationBotStatusRead(configured=True, **description)


@router.post("/notification-bot/probe", response_model=NotificationBotProbeRead)
async def probe_notification_bot(
    payload: NotificationBotProbeRequest, request: Request
) -> NotificationBotProbeRead:
    try:
        bot, chats = await _bot(request).inspect(payload.token.strip())
    except BotApiError as exc:
        raise _bot_error(exc) from exc
    return NotificationBotProbeRead(
        bot_username=bot.get("username"),
        bot_name=bot.get("first_name"),
        chats=[NotificationBotChatRead(**chat) for chat in chats],
    )


@router.post("/notification-bot", response_model=NotificationBotStatusRead)
async def configure_notification_bot(
    payload: NotificationBotConfigureRequest, request: Request
) -> NotificationBotStatusRead:
    try:
        result = await _bot(request).configure(payload.token.strip(), payload.chat_id)
    except BotApiError as exc:
        raise _bot_error(exc) from exc
    bot = result["bot"]
    chat = result["chat"]
    chat_title = chat.get("title") or " ".join(
        value for value in (chat.get("first_name"), chat.get("last_name")) if value
    )
    return NotificationBotStatusRead(
        configured=True,
        bot_username=bot.get("username"),
        bot_name=bot.get("first_name"),
        chat_id=payload.chat_id,
        chat_title=chat_title or chat.get("username") or payload.chat_id,
    )


@router.delete("/notification-bot", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_notification_bot(request: Request) -> None:
    _bot(request).disconnect()


async def get_or_create(db: AsyncSession) -> AppSettings:
    settings = await db.get(AppSettings, 1)
    if settings is None:
        settings = AppSettings(id=1, minimum_notification_score=get_settings().lead_score_threshold)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.get("", response_model=SettingsRead)
async def read_settings(db: DbSession) -> AppSettings:
    return await get_or_create(db)


@router.patch("", response_model=SettingsRead)
async def update_settings(
    payload: SettingsUpdate, db: DbSession
) -> AppSettings:
    settings = await get_or_create(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    await db.commit()
    await db.refresh(settings)
    return settings


@router.post("/cleanup-messages", response_model=MessageCleanupRead)
async def cleanup_messages(request: Request) -> MessageCleanupRead:
    result = await request.app.state.workers.cleanup.cleanup_now()
    return MessageCleanupRead(
        deleted_messages=result.deleted_messages,
        deleted_rejected_leads=result.deleted_rejected_leads,
        retention_days=result.retention_days,
        cutoff=result.cutoff,
    )
