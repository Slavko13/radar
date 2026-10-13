import asyncio
import logging

from app.config import Settings
from app.lead_detection.classifier import OpenAICompatibleClassifier
from app.notifications.bot import TelegramBotClient
from app.telegram.session_store import EncryptedSessionStore, SessionStoreError
from app.workers.bot_feedback import BotFeedbackWorker
from app.workers.discovery import DiscoveryWorker
from app.workers.lead_pipeline import LeadPipelineWorker
from app.workers.notifications import NotificationWorker

logger = logging.getLogger(__name__)


class WorkerCoordinator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = EncryptedSessionStore(
            settings.telegram_session_dir, settings.app_secret_key
        )
        try:
            stored_ai = self.store.read_ai_credentials()
        except SessionStoreError:
            logger.exception("ai_credentials_restore_failed")
            stored_ai = None
        if stored_ai:
            settings.ai_provider = stored_ai["provider"]
            settings.ai_api_key = stored_ai["api_key"]
            settings.ai_model = stored_ai["model"]
            settings.ai_base_url = stored_ai["base_url"]
        self.bot = TelegramBotClient(settings)
        self.pipeline = LeadPipelineWorker(settings)
        self.notifications = NotificationWorker(settings, self.bot)
        self.feedback = BotFeedbackWorker(settings, self.bot)
        self.discovery = DiscoveryWorker()
        self.tasks: list[asyncio.Task] = []

    async def configure_ai(
        self, provider: str, api_key: str, model: str, base_url: str
    ) -> None:
        candidate = self.settings.model_copy(
            update={
                "ai_provider": provider,
                "ai_api_key": api_key,
                "ai_model": model,
                "ai_base_url": base_url,
            }
        )
        classifier = OpenAICompatibleClassifier(candidate)
        try:
            await classifier.classify("Нужен разработчик лендинга, пишите @example_user")
        finally:
            await classifier.close()
        self.settings.ai_provider = provider
        self.settings.ai_api_key = api_key
        self.settings.ai_model = model
        self.settings.ai_base_url = base_url
        self.store.write_ai_credentials(provider, api_key, model, base_url)
        await self.pipeline.reconfigure()

    async def use_mock_ai(self) -> None:
        self.store.delete_ai_credentials()
        self.settings.ai_provider = "mock"
        self.settings.ai_api_key = None
        self.settings.ai_model = None
        await self.pipeline.reconfigure()

    async def start(self) -> None:
        self.tasks = [
            asyncio.create_task(self.pipeline.run(), name="lead-pipeline"),
            asyncio.create_task(self.notifications.run(), name="lead-notifications"),
            asyncio.create_task(self.feedback.run(), name="bot-feedback"),
            asyncio.create_task(self.discovery.run(), name="source-discovery"),
        ]
        logger.info("background_workers_started")

    async def stop(self) -> None:
        await self.pipeline.stop()
        await self.notifications.stop()
        await self.feedback.stop()
        await self.discovery.stop()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.bot.close()
        self.tasks.clear()
        logger.info("background_workers_stopped")
