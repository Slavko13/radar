from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import FeedbackValue, LeadStatus, SourceStatus, TelegramAccountStatus


class SourceCreate(BaseModel):
    title: str | None = None
    url: str | None = None
    username: str | None = None

    @field_validator("url", "username")
    @classmethod
    def strip_empty(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    def normalized_username(self) -> str | None:
        if self.username:
            return self.username.removeprefix("@").lower()
        if self.url and "t.me/" in self.url and "/+" not in self.url:
            return self.url.rstrip("/").rsplit("/", 1)[-1].lower()
        return None


class SourceUpdate(BaseModel):
    title: str | None = None
    status: SourceStatus | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    username: str | None
    url: str | None
    invite_url: str | None
    is_public: bool
    status: SourceStatus
    participants_count: int | None
    source_score: float | None
    created_at: datetime


class TelegramDialogImport(BaseModel):
    telegram_chat_id: int


class TelegramDialogRead(BaseModel):
    telegram_chat_id: int
    title: str
    username: str | None
    participants_count: int | None
    source_type: str
    source_id: int | None = None
    source_status: SourceStatus | None = None
    already_added: bool = False


class SourceStatsRead(BaseModel):
    messages_30d: int
    leads_30d: int
    confirmed_30d: int
    false_positive_30d: int
    source_score: float


class SourceAnalysisRequest(BaseModel):
    limit: int = Field(default=500)

    @field_validator("limit")
    @classmethod
    def valid_limit(cls, value: int) -> int:
        if value not in {100, 500, 1000}:
            raise ValueError("limit must be 100, 500, or 1000")
        return value


class SourceAnalysisRead(BaseModel):
    fetched: int
    inserted: int
    candidates: int
    source_score: float


class DiscoveryQueryCreate(BaseModel):
    query: str = Field(min_length=2, max_length=255)
    enabled: bool = True


class DiscoveryQueryUpdate(BaseModel):
    query: str | None = Field(default=None, min_length=2, max_length=255)
    enabled: bool | None = None


class DiscoveryQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    enabled: bool
    last_run_at: datetime | None
    created_at: datetime


class DiscoveryRunRead(BaseModel):
    queries_run: int
    found: int
    added: int


class SearchProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    enabled: bool = True
    categories: list[str] = Field(default_factory=list)
    positive_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    min_score: int = Field(default=70, ge=0, le=100)
    include_vacancies: bool = False
    notification_enabled: bool = True

    @field_validator("categories", "positive_keywords", "negative_keywords")
    @classmethod
    def normalize_list(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class SearchProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    enabled: bool | None = None
    categories: list[str] | None = None
    positive_keywords: list[str] | None = None
    negative_keywords: list[str] | None = None
    min_score: int | None = Field(default=None, ge=0, le=100)
    include_vacancies: bool | None = None
    notification_enabled: bool | None = None


class SearchProfileRead(SearchProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class FeedbackCreate(BaseModel):
    feedback: FeedbackValue


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feedback: FeedbackValue
    created_at: datetime


class DraftResponseRead(BaseModel):
    draft: str
    generated_at: datetime
    auto_sent: bool = False


class LeadRead(BaseModel):
    id: int
    message_id: int
    source_id: int
    source_title: str
    message_text: str
    message_url: str | None
    sender_username: str | None
    message_date: datetime
    confidence: float
    lead_score: int
    category: str
    service: str | None
    intent: str
    urgency: str | None
    budget: Decimal | None
    budget_currency: str | None
    deadline: date | None
    summary: str
    reason: str | None
    status: LeadStatus
    feedback: FeedbackValue | None
    created_at: datetime


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    minimum_notification_score: int
    include_vacancies: bool


class SettingsUpdate(BaseModel):
    minimum_notification_score: int | None = Field(default=None, ge=0, le=100)
    include_vacancies: bool | None = None


class DashboardRead(BaseModel):
    messages_today: int
    prefiltered_today: int
    ai_checked_today: int
    leads_today: int
    hot_today: int
    good_today: int
    possible_today: int
    confirmed_today: int


class PipelineStatusRead(BaseModel):
    pending: int
    retrying: int
    failed: int
    completed: int
    notifications_pending: int
    notifications_failed: int


class TelegramAuthStart(BaseModel):
    phone: str = Field(min_length=7, max_length=32, pattern=r"^\+?[0-9 ()-]+$")


class TelegramApiCredentials(BaseModel):
    api_id: int = Field(gt=0)
    api_hash: str = Field(min_length=32, max_length=64, pattern=r"^[a-fA-F0-9]+$")


class TelegramAuthCode(BaseModel):
    auth_token: str
    code: str = Field(min_length=3, max_length=10, pattern=r"^[0-9]+$")


class TelegramAuthPassword(BaseModel):
    auth_token: str
    password: str = Field(min_length=1, max_length=256)


class TelegramAuthChallenge(BaseModel):
    auth_token: str
    status: str


class TelegramStatusRead(BaseModel):
    configured: bool
    connected: bool
    status: TelegramAccountStatus | str
    phone: str | None = None
    username: str | None = None
    account_name: str | None = None


class IntegrationStatusRead(BaseModel):
    ai_configured: bool
    ai_provider: str
    ai_model: str | None
    notification_bot_configured: bool


class NotificationBotChatRead(BaseModel):
    chat_id: str
    title: str
    type: str


class NotificationBotProbeRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class NotificationBotProbeRead(BaseModel):
    bot_username: str | None = None
    bot_name: str | None = None
    chats: list[NotificationBotChatRead] = Field(default_factory=list)


class NotificationBotConfigureRequest(NotificationBotProbeRequest):
    chat_id: str = Field(min_length=1, max_length=64, pattern=r"^-?[0-9]+$")


class NotificationBotStatusRead(BaseModel):
    configured: bool
    bot_username: str | None = None
    bot_name: str | None = None
    chat_id: str | None = None
    chat_title: str | None = None
