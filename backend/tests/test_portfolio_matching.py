from types import SimpleNamespace

from app.services.portfolio_matching import match_portfolio


def test_matching_returns_only_grounded_portfolio_items() -> None:
    profile = SimpleNamespace(
        services=["разработка сайтов"],
        skills=["React", "Tilda"],
        desired_offer_types=["PROJECT_ORDER"],
    )
    items = [
        SimpleNamespace(
            id=1,
            title="Сайт агентства",
            description="Корпоративный сайт на React",
            url="https://example.test/case",
            services=["разработка сайтов"],
            skills=["React"],
        ),
        SimpleNamespace(
            id=2,
            title="Несвязанный бот",
            description="Telegram автоматизация",
            url=None,
            services=["боты"],
            skills=["Python"],
        ),
    ]

    result = match_portfolio(
        title="Нужна доработка сайта на React",
        summary="Ищем разработчика для корпоративного сайта",
        category="WEB_DEVELOPMENT",
        service="WEBSITE",
        requirements=["React"],
        offer_type="PROJECT_ORDER",
        profile=profile,
        items=items,
    )

    assert result.fit_score > 0
    assert [item["title"] for item in result.materials] == ["Сайт агентства"]
