import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, dashboard, discovery, leads, profiles, settings, sources, telegram
from app.auth.middleware import AdminAuthMiddleware
from app.auth.service import AuthService
from app.config import get_settings
from app.database import engine
from app.security import SecurityHeadersMiddleware
from app.telegram.manager import telegram_manager
from app.workers.coordinator import WorkerCoordinator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)
app_settings = get_settings()
app_settings.validate_security()
workers = WorkerCoordinator(app_settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("application_started")
    await telegram_manager.startup()
    await workers.start()
    try:
        yield
    finally:
        await workers.stop()
        await telegram_manager.shutdown()
        await engine.dispose()


app = FastAPI(
    title=app_settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if app_settings.is_production else "/docs",
    redoc_url=None if app_settings.is_production else "/redoc",
    openapi_url=None if app_settings.is_production else "/openapi.json",
)
app.state.workers = workers
app.add_middleware(AdminAuthMiddleware, auth=AuthService(app_settings))
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware, production=app_settings.is_production)
app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(telegram.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    database = "connected"
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database_healthcheck_failed")
        database = "unavailable"
    return {
        "status": "ok" if database == "connected" else "degraded",
        "database": database,
        "telegram": "connected" if telegram_manager.connected else "disconnected",
        "ai": "available" if app_settings.ai_configured else "not_configured",
        "notifications": "configured" if app_settings.notification_configured else "not_configured",
    }
