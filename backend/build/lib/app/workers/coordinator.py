import asyncio
import logging

from app.config import Settings
from app.notifications.bot import TelegramBotClient
from app.workers.bot_feedback import BotFeedbackWorker
from app.workers.lead_pipeline import LeadPipelineWorker
from app.workers.notifications import NotificationWorker

logger = logging.getLogger(__name__)


class WorkerCoordinator:
    def __init__(self, settings: Settings) -> None:
        self.bot = TelegramBotClient(settings)
        self.pipeline = LeadPipelineWorker(settings)
        self.notifications = NotificationWorker(settings, self.bot)
        self.feedback = BotFeedbackWorker(settings, self.bot)
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self.tasks = [
            asyncio.create_task(self.pipeline.run(), name="lead-pipeline"),
            asyncio.create_task(self.notifications.run(), name="lead-notifications"),
            asyncio.create_task(self.feedback.run(), name="bot-feedback"),
        ]
        logger.info("background_workers_started")

    async def stop(self) -> None:
        await self.pipeline.stop()
        await self.notifications.stop()
        await self.feedback.stop()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.bot.close()
        self.tasks.clear()
        logger.info("background_workers_stopped")
