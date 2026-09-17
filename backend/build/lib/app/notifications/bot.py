import asyncio
import html
import logging
from typing import Any

import httpx

from app.config import Settings
from app.models import Lead
from app.telegram.session_store import EncryptedSessionStore, SessionStoreError

logger = logging.getLogger(__name__)


class BotApiError(RuntimeError):
    pass


class TelegramBotClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = EncryptedSessionStore(
            settings.telegram_session_dir, settings.app_secret_key
        )
        try:
            stored = self.store.read_notification_bot()
        except SessionStoreError:
            logger.exception("notification_bot_credentials_restore_failed")
            stored = None
        if stored:
            settings.telegram_bot_token, settings.telegram_notification_chat_id = stored
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_notification_chat_id
        self.client = httpx.AsyncClient(timeout=35)
        self._updates_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    async def inspect(self, token: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        bot = await self._request_with_token(token, "getMe", {})
        async with self._updates_lock:
            updates = await self._request_with_token(
                token,
                "getUpdates",
                {"timeout": 0, "allowed_updates": ["message", "channel_post", "callback_query"]},
            )
        chats: dict[str, dict[str, Any]] = {}
        if isinstance(updates, list):
            for update in updates:
                if not isinstance(update, dict):
                    continue
                message = update.get("message") or update.get("channel_post")
                if not message and isinstance(update.get("callback_query"), dict):
                    message = update["callback_query"].get("message")
                chat = message.get("chat") if isinstance(message, dict) else None
                if not isinstance(chat, dict) or "id" not in chat:
                    continue
                title = chat.get("title") or " ".join(
                    value for value in (chat.get("first_name"), chat.get("last_name")) if value
                )
                chats[str(chat["id"])] = {
                    "chat_id": str(chat["id"]),
                    "title": title or chat.get("username") or str(chat["id"]),
                    "type": str(chat.get("type") or "unknown"),
                }
        return bot if isinstance(bot, dict) else {}, list(chats.values())

    async def configure(self, token: str, chat_id: str) -> dict[str, Any]:
        bot = await self._request_with_token(token, "getMe", {})
        chat = await self._request_with_token(token, "getChat", {"chat_id": chat_id})
        await self._request_with_token(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "✅ Lead Radar подключён. Уведомления будут приходить в этот чат.",
            },
        )
        self.store.write_notification_bot(token, chat_id)
        self.token = token
        self.chat_id = chat_id
        self.settings.telegram_bot_token = token
        self.settings.telegram_notification_chat_id = chat_id
        logger.info("notification_bot_configured")
        return {
            "bot": bot if isinstance(bot, dict) else {},
            "chat": chat if isinstance(chat, dict) else {},
        }

    async def describe(self) -> dict[str, str | None]:
        if not self.token or not self.chat_id:
            raise BotApiError("Notification bot is not configured")
        bot = await self._request("getMe", {})
        chat = await self._request("getChat", {"chat_id": self.chat_id})
        bot_data = bot if isinstance(bot, dict) else {}
        chat_data = chat if isinstance(chat, dict) else {}
        chat_title = chat_data.get("title") or " ".join(
            value
            for value in (chat_data.get("first_name"), chat_data.get("last_name"))
            if value
        )
        return {
            "bot_username": bot_data.get("username"),
            "bot_name": bot_data.get("first_name"),
            "chat_id": str(self.chat_id),
            "chat_title": chat_title or chat_data.get("username") or str(self.chat_id),
        }

    def disconnect(self) -> None:
        self.store.delete_notification_bot()
        self.token = None
        self.chat_id = None
        self.settings.telegram_bot_token = None
        self.settings.telegram_notification_chat_id = None
        logger.info("notification_bot_disconnected")

    async def close(self) -> None:
        await self.client.aclose()

    async def send_lead(self, lead: Lead) -> None:
        if not self.configured:
            raise BotApiError("Notification bot is not configured")
        message = lead.message
        source = message.source
        author = f"@{message.sender_username}" if message.sender_username else message.sender_name
        budget = (
            f"{lead.budget} {lead.budget_currency or ''}".strip()
            if lead.budget is not None
            else "Не указан"
        )
        deadline = lead.deadline.isoformat() if lead.deadline else "Не указан"
        text = (
            f"🔥 <b>НОВЫЙ ЛИД — {lead.lead_score}/100</b>\n\n"
            f"{html.escape(lead.summary)}\n\n"
            f"<b>Категория:</b> {html.escape(lead.category.replace('_', ' ').title())}\n"
            f"<b>Срочность:</b> {html.escape(lead.urgency or 'Не указана')}\n"
            f"<b>Бюджет:</b> {html.escape(budget)}\n"
            f"<b>Срок:</b> {html.escape(deadline)}\n\n"
            f"<b>Чат:</b> {html.escape(source.title)}\n"
            f"<b>Автор:</b> {html.escape(author or 'Не указан')}"
        )
        buttons: list[list[dict[str, str]]] = []
        if message.message_url:
            buttons.append([{"text": "🚀 Открыть сообщение", "url": message.message_url}])
        buttons.append(
            [
                {"text": "✅ Хороший лид", "callback_data": f"lead:{lead.id}:positive"},
                {"text": "❌ Не лид", "callback_data": f"lead:{lead.id}:negative"},
            ]
        )
        await self._request(
            "sendMessage",
            {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": {"inline_keyboard": buttons},
            },
        )

    async def get_updates(self, offset: int | None) -> list[dict]:
        payload: dict[str, object] = {
            "timeout": 25,
            "allowed_updates": ["callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        async with self._updates_lock:
            result = await self._request("getUpdates", payload, timeout=30)
        return result if isinstance(result, list) else []

    async def answer_callback(self, callback_id: str, text: str) -> None:
        await self._request(
            "answerCallbackQuery",
            {"callback_query_id": callback_id, "text": text},
        )

    async def _request(
        self, method: str, payload: dict[str, object], timeout: float | None = None
    ) -> object:
        if not self.token:
            raise BotApiError("Notification bot is not configured")
        return await self._request_with_token(self.token, method, payload, timeout)

    async def _request_with_token(
        self, token: str, method: str, payload: dict[str, object], timeout: float | None = None
    ) -> object:
        try:
            response = await self.client.post(
                f"https://api.telegram.org/bot{token}/{method}",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise TypeError("Telegram Bot API response is not an object")
            if not body.get("ok"):
                raise ValueError("Telegram Bot API returned ok=false")
            return body.get("result")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise BotApiError("Telegram Bot API request failed") from exc
