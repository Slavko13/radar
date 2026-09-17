import pytest

from app.config import Settings
from app.lead_detection.reply_generator import generate_reply_draft


@pytest.mark.asyncio
async def test_mock_reply_is_a_draft_only() -> None:
    draft = await generate_reply_draft(
        Settings(ai_provider="mock"),
        {"service": "разработке сайта", "message": "Нужен сайт"},
    )

    assert "разработке сайта" in draft
    assert "Подскажите" in draft
