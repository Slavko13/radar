from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    JOIN_PENDING = "JOIN_PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REJECTED = "REJECTED"
    LEFT = "LEFT"
    UNAVAILABLE = "UNAVAILABLE"


class LeadStatus(StrEnum):
    NEW = "NEW"
    REVIEWED = "REVIEWED"
    AI_PROCESSING_FAILED = "AI_PROCESSING_FAILED"


class FeedbackValue(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class TelegramAccountStatus(StrEnum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    INVALID_SESSION = "INVALID_SESSION"


class MessageProcessingStatus(StrEnum):
    SKIPPED = "SKIPPED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    RETRY = "RETRY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    positive_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    negative_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    min_score: Mapped[int] = mapped_column(Integer, default=70)
    include_vacancies: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DiscoveryQuery(Base):
    __tablename__ = "discovery_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    query: Mapped[str] = mapped_column(String(255), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    phone: Mapped[str] = mapped_column(String(32))
    username: Mapped[str | None] = mapped_column(String(255))
    account_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[TelegramAccountStatus] = mapped_column(
        Enum(TelegramAccountStatus, native_enum=False), default=TelegramAccountStatus.CONNECTED
    )
    session_reference: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    type: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    invite_url: Mapped[str | None] = mapped_column(String(500))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    participants_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, native_enum=False), default=SourceStatus.REVIEW, index=True
    )
    source_score: Mapped[float | None] = mapped_column(Float)
    discovery_source: Mapped[str] = mapped_column(String(50), default="MANUAL")
    discovery_query: Mapped[str | None] = mapped_column(String(255))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="source")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("source_id", "telegram_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    matched_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    sender_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_username: Mapped[str | None] = mapped_column(String(255))
    sender_name: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    edit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    thread_id: Mapped[int | None] = mapped_column(BigInteger)
    reply_to_message_id: Mapped[int | None] = mapped_column(BigInteger)
    message_url: Mapped[str | None] = mapped_column(String(500))
    prefilter_result: Mapped[bool] = mapped_column(Boolean, index=True)
    processing_status: Mapped[MessageProcessingStatus] = mapped_column(
        Enum(MessageProcessingStatus, native_enum=False),
        default=MessageProcessingStatus.PENDING,
        index=True,
    )
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0)
    processing_next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[Source] = relationship(back_populates="messages")
    lead: Mapped["Lead | None"] = relationship(back_populates="message", uselist=False)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="SET NULL"), nullable=True
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    is_lead: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[float] = mapped_column(Float)
    lead_score: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    service: Mapped[str | None] = mapped_column(String(100))
    intent: Mapped[str] = mapped_column(String(50))
    urgency: Mapped[str | None] = mapped_column(String(20))
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    deadline: Mapped[date | None] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(String(500))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, native_enum=False), default=LeadStatus.NEW, index=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_attempts: Mapped[int] = mapped_column(Integer, default=0)
    notification_next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    message: Mapped[Message] = relationship(back_populates="lead")
    feedback: Mapped[list["LeadFeedback"]] = relationship(
        back_populates="lead", order_by="LeadFeedback.created_at"
    )


class LeadFeedback(Base):
    __tablename__ = "lead_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    bot_update_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    feedback: Mapped[FeedbackValue] = mapped_column(Enum(FeedbackValue, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lead: Mapped[Lead] = relationship(back_populates="feedback")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    minimum_notification_score: Mapped[int] = mapped_column(Integer, default=70)
    include_vacancies: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
