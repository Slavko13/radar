import hashlib
import re
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select

from app.models import Message

URL_RE = re.compile(r"https?://\S+|t\.me/\S+", re.IGNORECASE)
NON_WORD_RE = re.compile(r"[^\wа-яё]+", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d[\d\s.,]*\d|\d")


def normalize_message(text: str) -> str:
    normalized = URL_RE.sub(" ссылка ", text.casefold().replace("ё", "е"))
    normalized = NUMBER_RE.sub(" число ", normalized)
    return " ".join(NON_WORD_RE.sub(" ", normalized).split())


def message_fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_message(text).encode("utf-8")).hexdigest()


def message_similarity(first: str, second: str) -> float:
    left = normalize_message(first)
    right = normalize_message(second)
    if not left or not right:
        return 0.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left, right, autojunk=False).ratio()
    return max(jaccard, sequence)


async def find_similar_message(
    db,
    text: str,
    *,
    sender_id: int | None,
    lookback_days: int = 30,
    candidate_limit: int = 300,
) -> Message | None:
    normalized = normalize_message(text)
    if len(normalized) < 40:
        return None
    fingerprint = message_fingerprint(text)
    exact = (
        await db.scalars(
            select(Message)
            .where(Message.content_fingerprint == fingerprint)
            .order_by(Message.message_date.desc())
            .limit(1)
        )
    ).one_or_none()
    if exact:
        return exact

    candidates = (
        await db.scalars(
            select(Message)
            .where(Message.message_date >= datetime.now(UTC) - timedelta(days=lookback_days))
            .order_by(Message.message_date.desc())
            .limit(candidate_limit)
        )
    ).all()
    for candidate in candidates:
        candidate_normalized = normalize_message(candidate.text)
        length_ratio = min(len(normalized), len(candidate_normalized)) / max(
            len(normalized), len(candidate_normalized), 1
        )
        if length_ratio < 0.65:
            continue
        threshold = 0.84 if sender_id and candidate.sender_id == sender_id else 0.93
        if message_similarity(text, candidate.text) >= threshold:
            return candidate
    return None
