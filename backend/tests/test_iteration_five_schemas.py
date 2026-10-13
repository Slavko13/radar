import pytest
from pydantic import ValidationError

from app.schemas import (
    PortfolioProfileUpdate,
    SearchProfileCreate,
    SettingsUpdate,
    SourceAnalysisRequest,
)


def test_source_analysis_accepts_only_safe_batch_sizes() -> None:
    assert SourceAnalysisRequest(limit=500).limit == 500
    with pytest.raises(ValidationError):
        SourceAnalysisRequest(limit=250)


def test_search_profile_normalizes_keyword_lists() -> None:
    profile = SearchProfileCreate(
        name="Web leads",
        positive_keywords=[" сайт ", "сайт", "лендинг"],
        negative_keywords=["курс", ""],
    )

    assert profile.positive_keywords == ["сайт", "лендинг"]
    assert profile.negative_keywords == ["курс"]


def test_portfolio_profile_normalizes_lists_and_currency() -> None:
    profile = PortfolioProfileUpdate(
        services=[" сайты ", "сайты"], skills=["React", ""], budget_currency="rub"
    )

    assert profile.services == ["сайты"]
    assert profile.skills == ["React"]
    assert profile.budget_currency == "RUB"


def test_notification_settings_reject_too_frequent_digest() -> None:
    with pytest.raises(ValidationError):
        SettingsUpdate(digest_interval_minutes=5)
