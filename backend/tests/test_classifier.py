import pytest

from app.lead_detection.classifier import MockLeadClassifier
from app.lead_detection.schemas import LeadClassification, LeadIntent


@pytest.mark.asyncio
async def test_mock_classifier_returns_structured_lead() -> None:
    result = await MockLeadClassifier().classify(
        "Посоветуйте разработчика, который сможет сделать сайт компании"
    )

    assert result.is_lead is True
    assert result.category == "WEB_DEVELOPMENT"
    assert result.intent == "REQUEST_FOR_RECOMMENDATION"
    assert 0 <= result.confidence <= 1


def test_non_lead_forces_not_a_lead_intent() -> None:
    result = LeadClassification.model_validate(
        {
            "is_lead": False,
            "confidence": 0.9,
            "category": "OTHER",
            "service": None,
            "intent": "OTHER",
            "urgency": "UNKNOWN",
            "budget": None,
            "budget_currency": None,
            "deadline": None,
            "summary": "Это вакансия",
            "reason": "Поиск сотрудника в штат",
        }
    )
    assert result.intent == LeadIntent.NOT_A_LEAD


def test_all_structured_output_fields_are_required() -> None:
    schema = LeadClassification.model_json_schema()
    assert set(schema["required"]) == {
        "is_lead",
        "confidence",
        "category",
        "service",
        "intent",
        "urgency",
        "budget",
        "budget_currency",
        "deadline",
        "summary",
        "reason",
    }

