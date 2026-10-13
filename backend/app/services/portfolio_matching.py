import re
from dataclasses import dataclass

from app.models import PortfolioItem, PortfolioProfile


@dataclass(frozen=True)
class PortfolioMatch:
    fit_score: int
    materials: list[dict[str, str | int | None]]


def match_portfolio(
    *,
    title: str,
    summary: str,
    category: str,
    service: str | None,
    requirements: list[str],
    offer_type: str,
    profile: PortfolioProfile | None,
    items: list[PortfolioItem],
) -> PortfolioMatch:
    haystack = " ".join(
        [title, summary, category, service or "", *requirements]
    ).casefold()
    lead_tokens = _tokens(haystack)
    profile_terms = [*(profile.services if profile else []), *(profile.skills if profile else [])]
    profile_overlap = _overlap(lead_tokens, profile_terms)
    desired_type = not profile or not profile.desired_offer_types or (
        offer_type in profile.desired_offer_types
    )

    ranked: list[tuple[int, PortfolioItem, list[str]]] = []
    for item in items:
        terms = [*item.services, *item.skills]
        matched = sorted(term for term in terms if _term_matches(lead_tokens, term))
        text_overlap = len(_tokens(item.description) & lead_tokens)
        score = min(100, len(matched) * 24 + min(text_overlap, 5) * 6)
        if score:
            ranked.append((score, item, matched))
    ranked.sort(key=lambda value: (-value[0], value[1].title.casefold()))

    materials = [
        {
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "reason": (
                f"Совпадают навыки: {', '.join(matched[:4])}"
                if matched
                else "Кейс близок по содержанию задачи"
            ),
            "score": score,
        }
        for score, item, matched in ranked[:3]
    ]
    item_score = ranked[0][0] if ranked else 0
    fit_score = min(100, profile_overlap * 12 + item_score // 2 + (15 if desired_type else 0))
    return PortfolioMatch(fit_score=fit_score, materials=materials)


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-zа-яё0-9+#.-]{2,}", value.casefold())}


def _term_matches(tokens: set[str], term: str) -> bool:
    normalized = term.strip().casefold()
    return bool(normalized) and (
        normalized in tokens or any(normalized in token or token in normalized for token in tokens)
    )


def _overlap(tokens: set[str], terms: list[str]) -> int:
    return sum(1 for term in terms if _term_matches(tokens, term))
