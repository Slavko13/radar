"""Initial MVP schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("minimum_notification_score", sa.Integer(), nullable=False),
        sa.Column("include_vacancies", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("telegram_chat_id", sa.BigInteger(), unique=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("url", sa.String(500)),
        sa.Column("invite_url", sa.String(500)),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("participants_count", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_score", sa.Float()),
        sa.Column("discovery_source", sa.String(50), nullable=False),
        sa.Column("discovery_query", sa.String(255)),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sources_status", "sources", ["status"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_id", sa.BigInteger()),
        sa.Column("sender_username", sa.String(255)),
        sa.Column("sender_name", sa.String(255)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("message_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edit_date", sa.DateTime(timezone=True)),
        sa.Column("thread_id", sa.BigInteger()),
        sa.Column("reply_to_message_id", sa.BigInteger()),
        sa.Column("message_url", sa.String(500)),
        sa.Column("prefilter_result", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_id", "telegram_message_id", name="uq_source_message"),
    )
    op.create_index("ix_messages_prefilter_result", "messages", ["prefilter_result"])
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("is_lead", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("lead_score", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("service", sa.String(100)),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("urgency", sa.String(20)),
        sa.Column("budget", sa.Numeric(14, 2)),
        sa.Column("budget_currency", sa.String(3)),
        sa.Column("deadline", sa.Date()),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leads_lead_score", "leads", ["lead_score"])
    op.create_index("ix_leads_category", "leads", ["category"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_table(
        "lead_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("feedback", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lead_feedback")
    op.drop_table("leads")
    op.drop_table("messages")
    op.drop_table("sources")
    op.drop_table("app_settings")
    op.drop_table("users")

