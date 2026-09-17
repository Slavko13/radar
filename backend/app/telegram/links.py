import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class TelegramTarget:
    username: str | None = None
    invite_hash: str | None = None


def parse_telegram_target(value: str) -> TelegramTarget:
    cleaned = value.strip()
    if cleaned.startswith("@"):
        username = cleaned[1:]
        if re.fullmatch(r"[A-Za-z0-9_]{5,}", username):
            return TelegramTarget(username=username.lower())
        raise ValueError("Invalid Telegram username")
    if re.fullmatch(r"[A-Za-z0-9_]{5,}", cleaned):
        return TelegramTarget(username=cleaned.lower())

    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    if parsed.hostname not in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
        raise ValueError("Only t.me links are supported")
    path = parsed.path.strip("/")
    if path.startswith("+") and len(path) > 1:
        return TelegramTarget(invite_hash=path[1:])
    if path.startswith("joinchat/") and len(path) > len("joinchat/"):
        return TelegramTarget(invite_hash=path.removeprefix("joinchat/"))
    username = path.split("/", 1)[0]
    if re.fullmatch(r"[A-Za-z0-9_]{5,}", username):
        return TelegramTarget(username=username.lower())
    raise ValueError("Invalid Telegram link")


def message_link(username: str | None, chat_id: int, message_id: int) -> str | None:
    if username:
        return f"https://t.me/{username}/{message_id}"
    raw_chat_id = str(chat_id)
    if raw_chat_id.startswith("-100") and len(raw_chat_id) > 4:
        return f"https://t.me/c/{raw_chat_id[4:]}/{message_id}"
    return None
