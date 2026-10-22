import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import AppSettings, DiscoveryQuery, PortfolioProfile, SearchProfile

CONFIG_PATH = Path(__file__).with_name("marketing_setup.json")


async def apply_setup() -> dict[str, object]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    summary: dict[str, object] = {
        "version": config["version"],
        "profiles_upserted": 0,
        "profiles_disabled": 0,
        "queries_upserted": 0,
        "queries_disabled": 0,
        "portfolio_defaults_added": [],
    }

    async with SessionLocal() as db:
        settings = await db.get(AppSettings, 1)
        if settings is None:
            settings = AppSettings(id=1)
            db.add(settings)
        for field, value in config["settings"].items():
            setattr(settings, field, value)

        for name in config["disable_search_profiles"]:
            profile = await db.scalar(select(SearchProfile).where(SearchProfile.name == name))
            if profile is not None and profile.enabled:
                profile.enabled = False
                profile.notification_enabled = False
                summary["profiles_disabled"] += 1

        profile_fields = (
            "description",
            "enabled",
            "categories",
            "positive_keywords",
            "negative_keywords",
            "min_score",
            "include_vacancies",
            "notification_enabled",
        )
        for payload in config["search_profiles"]:
            profile = await db.scalar(
                select(SearchProfile).where(SearchProfile.name == payload["name"])
            )
            if profile is None:
                profile = SearchProfile(name=payload["name"])
                db.add(profile)
            for field in profile_fields:
                setattr(profile, field, payload[field])
            summary["profiles_upserted"] += 1

        for query_text in config["disable_discovery_queries"]:
            query = await db.scalar(
                select(DiscoveryQuery).where(DiscoveryQuery.query == query_text)
            )
            if query is not None and query.enabled:
                query.enabled = False
                summary["queries_disabled"] += 1

        for query_text in config["discovery_queries"]:
            query = await db.scalar(
                select(DiscoveryQuery).where(DiscoveryQuery.query == query_text)
            )
            if query is None:
                query = DiscoveryQuery(query=query_text)
                db.add(query)
            query.enabled = True
            summary["queries_upserted"] += 1

        portfolio = await db.get(PortfolioProfile, 1)
        if portfolio is None:
            portfolio = PortfolioProfile(id=1)
            db.add(portfolio)
        for field, value in config["portfolio_defaults"].items():
            current = getattr(portfolio, field)
            if current in (None, "", []):
                setattr(portfolio, field, value)
                summary["portfolio_defaults_added"].append(field)

        await db.commit()

    return summary


async def main() -> None:
    summary = await apply_setup()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
