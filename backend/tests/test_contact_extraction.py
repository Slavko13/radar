from app.services.contact_extraction import extract_lead_contact


def test_explicit_contact_near_instruction_has_priority() -> None:
    contact = extract_lead_contact(
        "Нужен дизайнер. По всем вопросам пишите @Design_Owner",
        sender_username="channel_admin",
        message_url="https://t.me/jobs/15",
    )

    assert contact is not None
    assert contact.value == "@design_owner"
    assert contact.source == "MESSAGE_USERNAME"
    assert contact.confidence == 0.98


def test_telegram_link_is_extracted() -> None:
    contact = extract_lead_contact("Отклик: https://t.me/project_owner")

    assert contact is not None
    assert contact.value == "@project_owner"
    assert contact.url == "https://t.me/project_owner"
    assert contact.source == "MESSAGE_LINK"


def test_sender_is_used_when_message_has_no_contact() -> None:
    contact = extract_lead_contact("Ищу разработчика сайта", sender_username="SiteOwner")

    assert contact is not None
    assert contact.value == "@siteowner"
    assert contact.source == "AUTHOR"


def test_message_link_is_safe_fallback() -> None:
    contact = extract_lead_contact(
        "Ищу разработчика сайта", message_url="https://t.me/c/123/456"
    )

    assert contact is not None
    assert contact.type == "MESSAGE_LINK"
    assert contact.confidence == 0.5


def test_hidden_contact_is_not_invented() -> None:
    assert extract_lead_contact("Ищу разработчика сайта") is None
