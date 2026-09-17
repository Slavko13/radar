import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from telethon import TelegramClient, events, utils
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    InviteRequestSentError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
    UserAlreadyParticipantError,
)
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import (
    AppSettings,
    Message,
    MessageProcessingStatus,
    SearchProfile,
    Source,
    SourceStatus,
    TelegramAccount,
    TelegramAccountStatus,
)
from app.services.prefilter import DEFAULT_SUBJECT_KEYWORDS, PrefilterResult, evaluate_message
from app.telegram.links import message_link, parse_telegram_target
from app.telegram.session_store import EncryptedSessionStore, SessionStoreError

logger = logging.getLogger(__name__)


class TelegramServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "TELEGRAM_ERROR",
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


@dataclass
class AuthAttempt:
    client: TelegramClient
    phone: str
    phone_code_hash: str
    created_at: float


@dataclass(frozen=True)
class JoinResult:
    status: SourceStatus
    telegram_chat_id: int | None = None
    title: str | None = None
    username: str | None = None
    participants_count: int | None = None
    source_type: str | None = None


@dataclass(frozen=True)
class PublicChatResult:
    telegram_chat_id: int
    title: str
    username: str
    participants_count: int | None
    source_type: str


@dataclass(frozen=True)
class JoinedChatResult:
    telegram_chat_id: int
    title: str
    username: str | None
    participants_count: int | None
    source_type: str


@dataclass(frozen=True)
class BackfillResult:
    fetched: int
    inserted: int
    candidates: int


class TelegramManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = EncryptedSessionStore(
            self.settings.telegram_session_dir, self.settings.app_secret_key
        )
        try:
            stored_credentials = self.store.read_api_credentials()
        except SessionStoreError:
            logger.exception("telegram_api_credentials_restore_failed")
            stored_credentials = None
        if stored_credentials:
            self.settings.telegram_api_id, self.settings.telegram_api_hash = stored_credentials
        self.client: TelegramClient | None = None
        self.auth_attempts: dict[str, AuthAttempt] = {}
        self._account_id: int | None = None
        self._client_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return self.settings.telegram_configured

    @property
    def connected(self) -> bool:
        return bool(self.client and self.client.is_connected())

    def _new_client(self, session: StringSession | None = None) -> TelegramClient:
        if not self.configured:
            raise TelegramServiceError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH are not configured",
                code="NOT_CONFIGURED",
            )
        if (
            self.settings.app_secret_key == "development-only-change-me"
            or len(self.settings.app_secret_key) < 32
        ):
            raise TelegramServiceError(
                "APP_SECRET_KEY must contain at least 32 characters before Telegram is connected",
                code="INSECURE_SESSION_KEY",
            )
        return TelegramClient(
            session or StringSession(),
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
            auto_reconnect=True,
            connection_retries=5,
            retry_delay=2,
        )

    def configure(self, api_id: int, api_hash: str) -> None:
        if self.connected and (
            api_id != self.settings.telegram_api_id
            or api_hash != self.settings.telegram_api_hash
        ):
            raise TelegramServiceError(
                "Disconnect the Telegram account before changing API credentials",
                code="ACCOUNT_CONNECTED",
            )
        self.store.write_api_credentials(api_id, api_hash)
        self.settings.telegram_api_id = api_id
        self.settings.telegram_api_hash = api_hash
        logger.info("telegram_api_credentials_configured")

    async def startup(self) -> None:
        if not self.configured:
            logger.info("telegram_not_configured")
            return
        async with SessionLocal() as db:
            account = (
                await db.scalars(
                    select(TelegramAccount)
                    .where(TelegramAccount.status == TelegramAccountStatus.CONNECTED)
                    .order_by(TelegramAccount.updated_at.desc())
                )
            ).first()
            if not account:
                return
            try:
                session = self.store.read(account.session_reference)
                client = self._new_client(StringSession(session))
                await client.connect()
                if not await client.is_user_authorized():
                    raise SessionStoreError("Telegram session is no longer authorized")
            except Exception:
                logger.exception(
                    "telegram_session_restore_failed", extra={"account_id": account.id}
                )
                account.status = TelegramAccountStatus.INVALID_SESSION
                await db.commit()
                return
            await self._adopt_client(client, account.id)
            logger.info("telegram_session_restored", extra={"account_id": account.id})

    async def shutdown(self) -> None:
        for attempt in list(self.auth_attempts.values()):
            await attempt.client.disconnect()
        self.auth_attempts.clear()
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def start_auth(self, phone: str) -> tuple[str, str]:
        self._prune_attempts()
        client = self._new_client()
        try:
            await client.connect()
            sent_code = await client.send_code_request(phone)
        except FloodWaitError as exc:
            await client.disconnect()
            raise TelegramServiceError(
                "Telegram rate limit reached", code="FLOOD_WAIT", retry_after=exc.seconds
            ) from exc
        except Exception as exc:
            await client.disconnect()
            raise TelegramServiceError("Could not send Telegram authorization code") from exc
        auth_token = secrets.token_urlsafe(32)
        self.auth_attempts[auth_token] = AuthAttempt(
            client=client,
            phone=phone,
            phone_code_hash=sent_code.phone_code_hash,
            created_at=time.monotonic(),
        )
        return auth_token, _mask_phone(phone)

    async def submit_code(self, auth_token: str, code: str) -> str:
        attempt = self._get_attempt(auth_token)
        try:
            await attempt.client.sign_in(
                phone=attempt.phone, code=code, phone_code_hash=attempt.phone_code_hash
            )
        except SessionPasswordNeededError:
            return "PASSWORD_REQUIRED"
        except PhoneCodeInvalidError as exc:
            raise TelegramServiceError("Invalid Telegram code", code="INVALID_CODE") from exc
        except PhoneCodeExpiredError as exc:
            await self._discard_attempt(auth_token)
            raise TelegramServiceError("Telegram code expired", code="CODE_EXPIRED") from exc
        await self._complete_auth(auth_token, attempt)
        return "CONNECTED"

    async def submit_password(self, auth_token: str, password: str) -> str:
        attempt = self._get_attempt(auth_token)
        try:
            await attempt.client.sign_in(password=password)
        except PasswordHashInvalidError as exc:
            raise TelegramServiceError(
                "Invalid Telegram 2FA password", code="INVALID_PASSWORD"
            ) from exc
        await self._complete_auth(auth_token, attempt)
        return "CONNECTED"

    async def _complete_auth(self, auth_token: str, attempt: AuthAttempt) -> None:
        me = await attempt.client.get_me()
        session_value = attempt.client.session.save()
        reference = self.store.write(me.id, session_value)
        account_name = " ".join(filter(None, [me.first_name, me.last_name])) or None
        async with SessionLocal() as db:
            account = (
                await db.scalars(
                    select(TelegramAccount).where(TelegramAccount.telegram_user_id == me.id)
                )
            ).one_or_none()
            if account is None:
                account = TelegramAccount(
                    telegram_user_id=me.id,
                    phone=attempt.phone,
                    username=me.username,
                    account_name=account_name,
                    status=TelegramAccountStatus.CONNECTED,
                    session_reference=reference,
                )
                db.add(account)
            else:
                account.phone = attempt.phone
                account.username = me.username
                account.account_name = account_name
                account.status = TelegramAccountStatus.CONNECTED
                account.session_reference = reference
            await db.flush()
            previous_accounts = (
                await db.scalars(
                    select(TelegramAccount).where(
                        TelegramAccount.id != account.id,
                        TelegramAccount.status == TelegramAccountStatus.CONNECTED,
                    )
                )
            ).all()
            for previous in previous_accounts:
                previous.status = TelegramAccountStatus.DISCONNECTED
                self.store.delete(previous.session_reference)
            await db.commit()
            await db.refresh(account)
            account_id = account.id
        self.auth_attempts.pop(auth_token, None)
        await self._adopt_client(attempt.client, account_id)
        logger.info("telegram_authorized", extra={"account_id": account_id})

    async def _adopt_client(self, client: TelegramClient, account_id: int) -> None:
        async with self._client_lock:
            if self.client and self.client is not client:
                await self.client.disconnect()
            self.client = client
            self._account_id = account_id
            client.add_event_handler(self._handle_new_message, events.NewMessage())

    async def disconnect(self) -> None:
        async with SessionLocal() as db:
            account = await db.get(TelegramAccount, self._account_id) if self._account_id else None
            if account is None:
                account = (
                    await db.scalars(
                        select(TelegramAccount).order_by(TelegramAccount.updated_at.desc())
                    )
                ).first()
            if account:
                reference = account.session_reference
                account.status = TelegramAccountStatus.DISCONNECTED
                await db.commit()
                self.store.delete(reference)
        if self.client:
            try:
                await self.client.log_out()
            finally:
                await self.client.disconnect()
                self.client = None
                self._account_id = None
        logger.info("telegram_disconnected")

    async def join_source(self, source: Source) -> JoinResult:
        client = self._authorized_client()
        try:
            target = parse_telegram_target(source.invite_url or source.url or source.username or "")
            if target.invite_hash:
                try:
                    updates = await client(ImportChatInviteRequest(target.invite_hash))
                    entity = updates.chats[0]
                except InviteRequestSentError:
                    return JoinResult(status=SourceStatus.JOIN_PENDING)
                except UserAlreadyParticipantError:
                    invite = await client(CheckChatInviteRequest(target.invite_hash))
                    entity = getattr(invite, "chat", None)
                    if entity is None:
                        raise TelegramServiceError(
                            "Already joined, but chat cannot be resolved"
                        ) from None
            else:
                entity = await client.get_entity(target.username)
                try:
                    await client(JoinChannelRequest(entity))
                except UserAlreadyParticipantError:
                    pass
            return _join_result(entity)
        except FloodWaitError as exc:
            raise TelegramServiceError(
                "Telegram rate limit reached", code="FLOOD_WAIT", retry_after=exc.seconds
            ) from exc
        except (InviteHashExpiredError, InviteHashInvalidError) as exc:
            raise TelegramServiceError(
                "Telegram invite link is invalid or expired", code="INVALID_INVITE"
            ) from exc
        except ChannelPrivateError as exc:
            raise TelegramServiceError(
                "Telegram source is unavailable", code="UNAVAILABLE"
            ) from exc

    async def search_public_chats(
        self, query: str, *, limit: int = 20
    ) -> list[PublicChatResult]:
        client = self._authorized_client()
        try:
            result = await client(SearchRequest(q=query, limit=min(max(limit, 1), 100)))
        except FloodWaitError as exc:
            raise TelegramServiceError(
                "Telegram rate limit reached", code="FLOOD_WAIT", retry_after=exc.seconds
            ) from exc
        chats: list[PublicChatResult] = []
        for entity in result.chats:
            username = getattr(entity, "username", None)
            if not username:
                continue
            source_type = "SUPERGROUP" if getattr(entity, "megagroup", False) else "CHANNEL"
            chats.append(
                PublicChatResult(
                    telegram_chat_id=utils.get_peer_id(entity),
                    title=getattr(entity, "title", username),
                    username=username.lower(),
                    participants_count=getattr(entity, "participants_count", None),
                    source_type=source_type,
                )
            )
        return chats

    async def list_joined_chats(self, *, limit: int = 500) -> list[JoinedChatResult]:
        client = self._authorized_client()
        chats: list[JoinedChatResult] = []
        try:
            async for dialog in client.iter_dialogs(limit=limit):
                if not (dialog.is_group or dialog.is_channel):
                    continue
                entity = dialog.entity
                username = getattr(entity, "username", None)
                source_type = "GROUP"
                if getattr(entity, "megagroup", False):
                    source_type = "SUPERGROUP"
                elif getattr(entity, "broadcast", False):
                    source_type = "CHANNEL"
                chats.append(
                    JoinedChatResult(
                        telegram_chat_id=utils.get_peer_id(entity),
                        title=dialog.name or username or "Telegram chat",
                        username=username.lower() if username else None,
                        participants_count=getattr(entity, "participants_count", None),
                        source_type=source_type,
                    )
                )
        except FloodWaitError as exc:
            raise TelegramServiceError(
                "Telegram rate limit reached", code="FLOOD_WAIT", retry_after=exc.seconds
            ) from exc
        return chats

    async def get_joined_chat(self, telegram_chat_id: int) -> JoinedChatResult:
        chats = await self.list_joined_chats()
        for chat in chats:
            if chat.telegram_chat_id == telegram_chat_id:
                return chat
        raise TelegramServiceError(
            "Chat is not present in the connected Telegram account",
            code="UNAVAILABLE",
        )

    async def backfill_source(self, source: Source, *, limit: int) -> BackfillResult:
        client = self._authorized_client()
        target = source.username or source.telegram_chat_id
        if target is None:
            raise TelegramServiceError("Telegram source is not resolved", code="UNAVAILABLE")
        fetched = 0
        inserted = 0
        candidates = 0
        try:
            entity = await client.get_entity(target)
            async with SessionLocal() as db:
                stored_source = await db.get(Source, source.id)
                if stored_source is None:
                    raise TelegramServiceError("Source not found", code="UNAVAILABLE")
                async for telegram_message in client.iter_messages(entity, limit=limit):
                    fetched += 1
                    text = (telegram_message.raw_text or "").strip()
                    if not text:
                        continue
                    sender = await telegram_message.get_sender()
                    try:
                        async with db.begin_nested():
                            was_inserted, was_candidate = await self._persist_message(
                                db,
                                stored_source,
                                telegram_message,
                                sender,
                                stored_source.telegram_chat_id or utils.get_peer_id(entity),
                            )
                    except IntegrityError:
                        was_inserted, was_candidate = False, False
                    inserted += int(was_inserted)
                    candidates += int(was_candidate)
                await db.commit()
        except FloodWaitError as exc:
            raise TelegramServiceError(
                "Telegram rate limit reached", code="FLOOD_WAIT", retry_after=exc.seconds
            ) from exc
        except ChannelPrivateError as exc:
            raise TelegramServiceError(
                "Telegram source is unavailable", code="UNAVAILABLE"
            ) from exc
        logger.info(
            "telegram_backfill_completed",
            extra={
                "source_id": source.id,
                "fetched": fetched,
                "inserted": inserted,
                "candidates": candidates,
            },
        )
        return BackfillResult(fetched=fetched, inserted=inserted, candidates=candidates)

    async def _handle_new_message(self, event) -> None:
        text = (event.raw_text or "").strip()
        if not text:
            return
        chat_id = event.chat_id
        async with SessionLocal() as db:
            source = (
                await db.scalars(
                    select(Source).where(
                        Source.telegram_chat_id == chat_id, Source.status == SourceStatus.ACTIVE
                    )
                )
            ).one_or_none()
            if not source:
                return
            source_id = source.id
            telegram_message_id = event.message.id
            sender = await event.get_sender()
            try:
                inserted, passed = await self._persist_message(
                    db, source, event.message, sender, chat_id
                )
                await db.commit()
            except IntegrityError:
                await db.rollback()
                logger.debug(
                    "telegram_message_duplicate",
                    extra={
                        "source_id": source_id,
                        "telegram_message_id": telegram_message_id,
                    },
                )
                return
            if not inserted:
                return
            logger.info(
                "telegram_message_received",
                extra={"source_id": source_id, "prefilter_passed": passed},
            )

    async def _persist_message(
        self, db, source: Source, telegram_message, sender, chat_id: int
    ) -> tuple[bool, bool]:
        existing = (
            await db.scalars(
                select(Message).where(
                Message.source_id == source.id,
                Message.telegram_message_id == telegram_message.id,
            )
            )
        ).one_or_none()
        if existing:
            if existing.processing_status == MessageProcessingStatus.SKIPPED:
                prefilter, profile_id = await _evaluate_for_profiles(db, existing.text)
                if prefilter.passed:
                    existing.prefilter_result = True
                    existing.matched_profile_id = profile_id
                    existing.processing_status = MessageProcessingStatus.PENDING
                    return False, True
            return False, False
        text = (telegram_message.raw_text or "").strip()
        prefilter, profile_id = await _evaluate_for_profiles(db, text)
        reply = telegram_message.reply_to
        message = Message(
            source_id=source.id,
            matched_profile_id=profile_id,
            telegram_message_id=telegram_message.id,
            sender_id=getattr(sender, "id", None),
            sender_username=getattr(sender, "username", None),
            sender_name=_sender_name(sender),
            text=text,
            message_date=telegram_message.date.astimezone(UTC),
            edit_date=telegram_message.edit_date,
            thread_id=getattr(reply, "reply_to_top_id", None),
            reply_to_message_id=getattr(reply, "reply_to_msg_id", None),
            message_url=message_link(source.username, chat_id, telegram_message.id),
            prefilter_result=prefilter.passed,
            processing_status=(
                MessageProcessingStatus.PENDING
                if prefilter.passed
                else MessageProcessingStatus.SKIPPED
            ),
        )
        message_date = telegram_message.date.astimezone(UTC)
        if source.last_message_at is None or message_date > source.last_message_at:
            source.last_message_at = message_date
        db.add(message)
        await db.flush()
        return True, prefilter.passed

    def _authorized_client(self) -> TelegramClient:
        if not self.client or not self.client.is_connected():
            raise TelegramServiceError("Telegram account is not connected", code="NOT_CONNECTED")
        return self.client

    def _get_attempt(self, auth_token: str) -> AuthAttempt:
        self._prune_attempts()
        attempt = self.auth_attempts.get(auth_token)
        if not attempt:
            raise TelegramServiceError("Authorization attempt expired", code="AUTH_EXPIRED")
        return attempt

    async def _discard_attempt(self, auth_token: str) -> None:
        attempt = self.auth_attempts.pop(auth_token, None)
        if attempt:
            await attempt.client.disconnect()

    def _prune_attempts(self) -> None:
        expired = [
            token
            for token, attempt in self.auth_attempts.items()
            if time.monotonic() - attempt.created_at > 600
        ]
        for token in expired:
            attempt = self.auth_attempts.pop(token)
            asyncio.create_task(attempt.client.disconnect())


def _mask_phone(phone: str) -> str:
    digits = "".join(char for char in phone if char.isdigit())
    return f"***{digits[-4:]}" if digits else "***"


def _sender_name(sender) -> str | None:
    if sender is None:
        return None
    parts = [getattr(sender, "first_name", None), getattr(sender, "last_name", None)]
    return " ".join(filter(None, parts)) or getattr(sender, "title", None)


def _join_result(entity) -> JoinResult:
    if entity is None:
        raise TelegramServiceError("Telegram source cannot be resolved")
    source_type = "SUPERGROUP" if getattr(entity, "megagroup", False) else "CHANNEL"
    if not getattr(entity, "broadcast", False) and not getattr(entity, "megagroup", False):
        source_type = "GROUP"
    return JoinResult(
        status=SourceStatus.ACTIVE,
        telegram_chat_id=utils.get_peer_id(entity),
        title=getattr(entity, "title", None),
        username=getattr(entity, "username", None),
        participants_count=getattr(entity, "participants_count", None),
        source_type=source_type,
    )


async def _evaluate_for_profiles(db, text: str) -> tuple[PrefilterResult, int | None]:
    profiles = (
        await db.scalars(
            select(SearchProfile)
            .where(SearchProfile.enabled.is_(True))
            .order_by(SearchProfile.id)
        )
    ).all()
    if profiles:
        last_result = PrefilterResult(False, (), (), ())
        for profile in profiles:
            subjects = tuple(profile.positive_keywords) or DEFAULT_SUBJECT_KEYWORDS
            result = evaluate_message(
                text,
                include_vacancies=profile.include_vacancies,
                require_intent=not bool(profile.positive_keywords),
                minimum_length=1 if profile.positive_keywords else 10,
                subject_keywords=subjects,
                negative_keywords=tuple(profile.negative_keywords),
            )
            if result.passed:
                return result, profile.id
            last_result = result
        return last_result, None
    app_settings = await db.get(AppSettings, 1)
    result = evaluate_message(
        text, include_vacancies=bool(app_settings and app_settings.include_vacancies)
    )
    return result, None


telegram_manager = TelegramManager()
