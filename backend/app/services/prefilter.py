import re
from dataclasses import dataclass

DEFAULT_INTENT_KEYWORDS = (
    "нужен",
    "нужна",
    "нужно",
    "ищу",
    "ищем",
    "требуется",
    "посоветуйте",
    "порекомендуйте",
    "кто может",
    "кто сделает",
    "кто занимается",
    "подрядчик",
    "специалист",
    "команда",
    "заказать",
    "разработать",
    "сделать",
    "доработать",
    "автоматизировать",
    "интегрировать",
)

DEFAULT_SUBJECT_KEYWORDS = (
    "сайт",
    "лендинг",
    "интернет-магазин",
    "приложение",
    "telegram bot",
    "телеграм бот",
    "бот",
    "crm",
    "1с",
    "api",
    "интеграц",
    "автоматизац",
    "ai",
    "llm",
    "нейросет",
    "тестирован",
    "дизайн",
    "frontend",
    "backend",
    "разработ",
)

VACANCY_PATTERNS = (
    "вакансия",
    "в штат",
    "полная занятость",
    "резюме",
    "hh.ru",
)

SELF_PROMOTION_PATTERNS = (
    "я разработчик",
    "беру новые проекты",
    "предлагаю услуги",
    "продам курс",
)


@dataclass(frozen=True)
class PrefilterResult:
    passed: bool
    intent_matches: tuple[str, ...]
    subject_matches: tuple[str, ...]
    negative_matches: tuple[str, ...]


def _matches(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    return tuple(keyword for keyword in keywords if keyword in normalized)


def evaluate_message(
    text: str,
    *,
    include_vacancies: bool = False,
    require_intent: bool = True,
    minimum_length: int = 10,
    intent_keywords: tuple[str, ...] = DEFAULT_INTENT_KEYWORDS,
    subject_keywords: tuple[str, ...] = DEFAULT_SUBJECT_KEYWORDS,
    negative_keywords: tuple[str, ...] = (),
) -> PrefilterResult:
    if not text or len(text.strip()) < minimum_length:
        return PrefilterResult(False, (), (), ())

    intents = _matches(text, intent_keywords)
    subjects = _matches(text, subject_keywords)
    negatives = _matches(text, SELF_PROMOTION_PATTERNS)
    negatives += _matches(text, negative_keywords)
    if not include_vacancies:
        negatives += _matches(text, VACANCY_PATTERNS)

    return PrefilterResult(
        bool((intents or not require_intent) and subjects and not negatives),
        intents,
        subjects,
        negatives,
    )
