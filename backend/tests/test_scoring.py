from app.services.scoring import ScoreFactors, calculate_lead_score, score_band


def test_strong_lead_scores_hot() -> None:
    score = calculate_lead_score(
        ScoreFactors(
            confidence=0.96,
            intent="LOOKING_FOR_CONTRACTOR",
            has_specific_task=True,
            has_budget=True,
            has_deadline=True,
            urgency="HIGH",
            source_score=8.0,
        )
    )
    assert score == 98
    assert score_band(score) == "HOT"


def test_score_is_clamped() -> None:
    assert calculate_lead_score(ScoreFactors(confidence=-1, intent="NOT_A_LEAD")) == 0
    assert calculate_lead_score(
        ScoreFactors(confidence=1, intent="LOOKING_FOR_CONTRACTOR", negative_signals=20)
    ) == 0


def test_score_bands() -> None:
    assert [score_band(value) for value in (90, 75, 60, 59)] == [
        "HOT",
        "GOOD",
        "POSSIBLE",
        "IGNORE",
    ]
