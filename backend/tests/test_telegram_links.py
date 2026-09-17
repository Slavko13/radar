import pytest

from app.telegram.links import message_link, parse_telegram_target


@pytest.mark.parametrize(
    ("value", "username"),
    [
        ("@ExampleChat", "examplechat"),
        ("ExampleChat", "examplechat"),
        ("https://t.me/ExampleChat", "examplechat"),
        ("t.me/ExampleChat/42", "examplechat"),
    ],
)
def test_parses_public_source(value: str, username: str) -> None:
    assert parse_telegram_target(value).username == username


@pytest.mark.parametrize(
    "value", ["https://t.me/+secretHash", "https://t.me/joinchat/secretHash"]
)
def test_parses_invite(value: str) -> None:
    assert parse_telegram_target(value).invite_hash == "secretHash"


def test_rejects_non_telegram_domain() -> None:
    with pytest.raises(ValueError):
        parse_telegram_target("https://example.com/t.me/fakechat")


def test_builds_public_and_private_message_links() -> None:
    assert message_link("examplechat", -100123456, 17) == "https://t.me/examplechat/17"
    assert message_link(None, -100123456, 17) == "https://t.me/c/123456/17"
    assert message_link(None, -123456, 17) is None
