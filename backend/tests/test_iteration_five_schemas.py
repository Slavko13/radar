import pytest
from pydantic import ValidationError

from app.schemas import SearchProfileCreate, SourceAnalysisRequest


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
