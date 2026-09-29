from app.services.message_quality import (
    message_fingerprint,
    message_similarity,
    normalize_message,
)


def test_normalization_ignores_links_case_and_numbers() -> None:
    first = "СОЗДАЁМ сайты! Цена 50 000 ₽ https://example.com/portfolio"
    second = "создаем сайты, цена 99999 — t.me/example"

    assert normalize_message(first) == normalize_message(second)
    assert message_fingerprint(first) == message_fingerprint(second)


def test_similar_broadcasts_are_detected() -> None:
    first = "Разрабатываем современные сайты для бизнеса под ключ. Пишите нам в личные сообщения."
    second = "Разрабатываем современные сайты для вашего бизнеса под ключ — напишите нам в личку."

    assert message_similarity(first, second) >= 0.84


def test_different_customer_requests_are_not_duplicates() -> None:
    first = "Ищу разработчика сайта для небольшой кофейни, нужен каталог и форма заказа."
    second = "Нужен специалист по Telegram-боту для автоматизации заявок отдела продаж."

    assert message_similarity(first, second) < 0.84
