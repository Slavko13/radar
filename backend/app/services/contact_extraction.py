import re
from dataclasses import dataclass

USERNAME_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z][A-Za-z0-9_]{4,31})\b")
TELEGRAM_LINK_PATTERN = re.compile(
    r"(?:(?:https?://)?(?:t\.me|telegram\.me)/)([A-Za-z][A-Za-z0-9_]{4,31})\b",
    re.IGNORECASE,
)
CONTACT_MARKERS = (
    "пиш",
    "напиш",
    "связаться",
    "связь",
    "контакт",
    "личку",
    "лс",
    "отклик",
)
RESERVED_USERNAMES = {
    "addlist",
    "addstickers",
    "boost",
    "c",
    "confirmphone",
    "joinchat",
    "login",
    "proxy",
    "setlanguage",
    "share",
    "socks",
}


@dataclass(frozen=True)
class ExtractedContact:
    type: str
    value: str
    url: str
    source: str
    confidence: float


def extract_lead_contact(
    text: str,
    *,
    sender_username: str | None = None,
    message_url: str | None = None,
) -> ExtractedContact | None:
    """Return the best contact Telegram exposes without inferring private data."""
    candidates: dict[str, tuple[float, str]] = {}
    for match in USERNAME_PATTERN.finditer(text):
        _add_candidate(candidates, match.group(1), text, match.start(), "MESSAGE_USERNAME")
    for match in TELEGRAM_LINK_PATTERN.finditer(text):
        _add_candidate(candidates, match.group(1), text, match.start(), "MESSAGE_LINK")

    if candidates:
        username, (confidence, source) = max(
            candidates.items(), key=lambda item: (item[1][0], -text.casefold().find(item[0]))
        )
        return _username_contact(username, source, confidence)

    normalized_sender = _normalize_username(sender_username)
    if normalized_sender:
        return _username_contact(normalized_sender, "AUTHOR", 0.9)

    if message_url:
        return ExtractedContact(
            type="MESSAGE_LINK",
            value="Исходное сообщение",
            url=message_url,
            source="MESSAGE",
            confidence=0.5,
        )
    return None


def _add_candidate(
    candidates: dict[str, tuple[float, str]],
    raw_username: str,
    text: str,
    position: int,
    source: str,
) -> None:
    username = _normalize_username(raw_username)
    if not username:
        return
    context = text[max(0, position - 60) : position + len(raw_username) + 60].casefold()
    confidence = 0.98 if any(marker in context for marker in CONTACT_MARKERS) else 0.82
    previous = candidates.get(username)
    if previous is None or confidence > previous[0]:
        candidates[username] = (confidence, source)


def _normalize_username(value: str | None) -> str | None:
    if not value:
        return None
    username = value.strip().removeprefix("@").casefold()
    if not re.fullmatch(r"[a-z][a-z0-9_]{4,31}", username):
        return None
    if username in RESERVED_USERNAMES:
        return None
    return username


def _username_contact(username: str, source: str, confidence: float) -> ExtractedContact:
    return ExtractedContact(
        type="TELEGRAM_USERNAME",
        value=f"@{username}",
        url=f"https://t.me/{username}",
        source=source,
        confidence=confidence,
    )
