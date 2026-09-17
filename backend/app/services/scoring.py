from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreFactors:
    confidence: float
    intent: str
    has_specific_task: bool = False
    has_budget: bool = False
    has_deadline: bool = False
    urgency: str | None = None
    source_score: float | None = None
    negative_signals: int = 0


def calculate_lead_score(factors: ScoreFactors) -> int:
    """Transparent MVP formula; weights can later move into Search Profile config."""
    score = round(max(0.0, min(1.0, factors.confidence)) * 40)

    if factors.intent in {
        "LOOKING_FOR_CONTRACTOR",
        "LOOKING_FOR_SPECIALIST",
        "REQUEST_FOR_RECOMMENDATION",
    }:
        score += 25
    elif factors.intent in {"REQUEST_FOR_ESTIMATE", "OUTSOURCING", "TENDER"}:
        score += 20
    elif factors.intent == "REQUEST_FOR_CONSULTATION":
        score += 12

    score += 12 if factors.has_specific_task else 0
    score += 8 if factors.has_budget else 0
    score += 6 if factors.has_deadline else 0
    score += {"HIGH": 5, "MEDIUM": 3, "LOW": 1}.get(factors.urgency or "", 0)
    if factors.source_score is not None:
        score += round(max(0.0, min(10.0, factors.source_score)) / 2)
    score -= factors.negative_signals * 15
    return max(0, min(100, score))


def score_band(score: int) -> str:
    if score >= 90:
        return "HOT"
    if score >= 75:
        return "GOOD"
    if score >= 60:
        return "POSSIBLE"
    return "IGNORE"

