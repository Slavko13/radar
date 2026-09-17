from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LeadCategory(StrEnum):
    WEB_DEVELOPMENT = "WEB_DEVELOPMENT"
    ECOMMERCE = "ECOMMERCE"
    MOBILE_DEVELOPMENT = "MOBILE_DEVELOPMENT"
    TELEGRAM_BOTS = "TELEGRAM_BOTS"
    CRM = "CRM"
    ERP_1C = "ERP_1C"
    INTEGRATIONS = "INTEGRATIONS"
    AUTOMATION = "AUTOMATION"
    AI_LLM = "AI_LLM"
    QA = "QA"
    DESIGN = "DESIGN"
    DEVOPS = "DEVOPS"
    DATA = "DATA"
    CONSULTING = "CONSULTING"
    OTHER = "OTHER"


class LeadIntent(StrEnum):
    LOOKING_FOR_CONTRACTOR = "LOOKING_FOR_CONTRACTOR"
    LOOKING_FOR_SPECIALIST = "LOOKING_FOR_SPECIALIST"
    REQUEST_FOR_RECOMMENDATION = "REQUEST_FOR_RECOMMENDATION"
    REQUEST_FOR_ESTIMATE = "REQUEST_FOR_ESTIMATE"
    REQUEST_FOR_CONSULTATION = "REQUEST_FOR_CONSULTATION"
    OUTSOURCING = "OUTSOURCING"
    TENDER = "TENDER"
    OTHER = "OTHER"
    NOT_A_LEAD = "NOT_A_LEAD"


class Urgency(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class LeadClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_lead: bool
    confidence: float = Field(ge=0, le=1)
    category: LeadCategory
    service: str | None = Field(max_length=100)
    intent: LeadIntent
    urgency: Urgency
    budget: Decimal | None = Field(ge=0)
    budget_currency: str | None = Field(min_length=3, max_length=3)
    deadline: date | None
    summary: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("budget_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @model_validator(mode="after")
    def lead_and_intent_are_consistent(self):
        if not self.is_lead:
            self.intent = LeadIntent.NOT_A_LEAD
        elif self.intent == LeadIntent.NOT_A_LEAD:
            self.is_lead = False
        return self
