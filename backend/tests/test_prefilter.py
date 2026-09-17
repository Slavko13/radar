from app.services.prefilter import evaluate_message


def test_lead_message_passes() -> None:
    result = evaluate_message("Посоветуйте разработчика, который сможет сделать сайт компании")
    assert result.passed is True
    assert "посоветуйте" in result.intent_matches
    assert "сайт" in result.subject_matches


def test_greeting_does_not_pass() -> None:
    assert evaluate_message("Всем доброе утро!").passed is False


def test_vacancy_is_rejected_by_default() -> None:
    result = evaluate_message("Нужен frontend разработчик в штат, открыта вакансия")
    assert result.passed is False
    assert "вакансия" in result.negative_matches


def test_vacancy_can_be_included() -> None:
    result = evaluate_message(
        "Нужен frontend разработчик в штат, открыта вакансия", include_vacancies=True
    )
    assert result.passed is True


def test_self_promotion_is_rejected() -> None:
    assert evaluate_message("Я разработчик сайтов, беру новые проекты").passed is False


def test_profile_negative_keyword_is_rejected() -> None:
    result = evaluate_message(
        "Нужен подрядчик, чтобы сделать сайт для казино",
        negative_keywords=("казино",),
    )
    assert result.passed is False
    assert "казино" in result.negative_matches


def test_profile_keyword_can_match_without_intent_and_short_text() -> None:
    result = evaluate_message(
        "мама",
        subject_keywords=("мама",),
        require_intent=False,
        minimum_length=1,
    )
    assert result.passed is True
    assert result.subject_matches == ("мама",)
