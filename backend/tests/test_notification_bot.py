from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.notifications.bot import TelegramBotClient


@pytest.mark.asyncio
async def test_notification_escapes_user_content_and_has_actions() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    bot = TelegramBotClient(
        Settings(telegram_bot_token="test-token", telegram_notification_chat_id="123")
    )
    await bot.client.aclose()
    bot.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = SimpleNamespace(title="Чат <test>")
    message = SimpleNamespace(
        source=source,
        sender_username="user",
        sender_name=None,
        message_url="https://t.me/example/1",
    )
    lead = SimpleNamespace(
        id=7,
        lead_score=94,
        summary="Нужен сайт <срочно>",
        category="WEB_DEVELOPMENT",
        urgency="HIGH",
        budget=None,
        budget_currency=None,
        deadline=None,
        message=message,
    )

    await bot.send_lead(lead)
    await bot.close()

    assert "&lt;срочно&gt;" in captured["text"]
    keyboard = captured["reply_markup"]["inline_keyboard"]
    assert keyboard[0][0]["url"] == "https://t.me/example/1"
    assert keyboard[1][0]["callback_data"] == "lead:7:positive"


@pytest.mark.asyncio
async def test_notification_bot_can_be_configured_without_restart(tmp_path) -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        methods.append(method)
        results = {
            "getMe": {"id": 1, "username": "lead_radar_bot", "first_name": "Lead Radar"},
            "getChat": {"id": 42, "first_name": "Owner", "type": "private"},
            "sendMessage": {"message_id": 1},
        }
        return httpx.Response(200, json={"ok": True, "result": results[method]})

    settings = Settings(
        telegram_bot_token=None,
        telegram_notification_chat_id=None,
        telegram_session_dir=str(tmp_path),
    )
    bot = TelegramBotClient(settings)
    await bot.client.aclose()
    bot.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    result = await bot.configure("123456:test-token", "42")

    assert methods == ["getMe", "getChat", "sendMessage"]
    assert result["bot"]["username"] == "lead_radar_bot"
    assert bot.configured
    assert settings.telegram_notification_chat_id == "42"
    assert bot.store.read_notification_bot() == ("123456:test-token", "42")
    await bot.close()
