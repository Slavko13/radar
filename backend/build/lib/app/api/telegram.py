from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.database import SessionLocal
from app.models import TelegramAccount
from app.schemas import (
    TelegramApiCredentials,
    TelegramAuthChallenge,
    TelegramAuthCode,
    TelegramAuthPassword,
    TelegramAuthStart,
    TelegramStatusRead,
)
from app.telegram.manager import TelegramServiceError, telegram_manager

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _http_error(exc: TelegramServiceError) -> HTTPException:
    status_code = status.HTTP_400_BAD_REQUEST
    headers = None
    if exc.code in {"NOT_CONFIGURED", "INSECURE_SESSION_KEY"}:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif exc.code in {"NOT_CONNECTED", "ACCOUNT_CONNECTED"}:
        status_code = status.HTTP_409_CONFLICT
    elif exc.code == "FLOOD_WAIT":
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        headers = {"Retry-After": str(exc.retry_after or 1)}
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": str(exc), "retry_after": exc.retry_after},
        headers=headers,
    )


@router.post("/configure", response_model=TelegramStatusRead)
async def configure_telegram(payload: TelegramApiCredentials) -> TelegramStatusRead:
    try:
        telegram_manager.configure(payload.api_id, payload.api_hash.lower())
    except TelegramServiceError as exc:
        raise _http_error(exc) from exc
    return TelegramStatusRead(
        configured=True,
        connected=telegram_manager.connected,
        status="CONNECTED" if telegram_manager.connected else "DISCONNECTED",
    )


def _mask_phone(phone: str) -> str:
    digits = "".join(char for char in phone if char.isdigit())
    return f"***{digits[-4:]}" if digits else "***"


@router.get("/status", response_model=TelegramStatusRead)
async def telegram_status() -> TelegramStatusRead:
    async with SessionLocal() as db:
        account = (
            await db.scalars(select(TelegramAccount).order_by(TelegramAccount.updated_at.desc()))
        ).first()
    if not account:
        return TelegramStatusRead(
            configured=telegram_manager.configured,
            connected=False,
            status="DISCONNECTED",
        )
    return TelegramStatusRead(
        configured=telegram_manager.configured,
        connected=telegram_manager.connected,
        status=account.status,
        phone=_mask_phone(account.phone),
        username=account.username,
        account_name=account.account_name,
    )


@router.post("/auth/start", response_model=TelegramAuthChallenge)
async def start_auth(payload: TelegramAuthStart) -> TelegramAuthChallenge:
    try:
        auth_token, _ = await telegram_manager.start_auth(payload.phone)
    except TelegramServiceError as exc:
        raise _http_error(exc) from exc
    return TelegramAuthChallenge(auth_token=auth_token, status="CODE_REQUIRED")


@router.post("/auth/code", response_model=TelegramAuthChallenge)
async def submit_code(payload: TelegramAuthCode) -> TelegramAuthChallenge:
    try:
        auth_status = await telegram_manager.submit_code(payload.auth_token, payload.code)
    except TelegramServiceError as exc:
        raise _http_error(exc) from exc
    return TelegramAuthChallenge(auth_token=payload.auth_token, status=auth_status)


@router.post("/auth/password", response_model=TelegramAuthChallenge)
async def submit_password(payload: TelegramAuthPassword) -> TelegramAuthChallenge:
    try:
        auth_status = await telegram_manager.submit_password(payload.auth_token, payload.password)
    except TelegramServiceError as exc:
        raise _http_error(exc) from exc
    return TelegramAuthChallenge(auth_token=payload.auth_token, status=auth_status)


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect() -> None:
    await telegram_manager.disconnect()
