"""Add durable AI processing and notification state."""

from alembic import op
import sqlalchemy as sa

revision = "0003_processing_pipeline"
down_revision = "0002_telegram_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("processing_status", sa.String(20), server_default="PENDING", nullable=False),
    )
    op.add_column(
        "messages",
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("messages", sa.Column("processing_next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("messages", sa.Column("processing_error", sa.String(255)))
    op.create_index("ix_messages_processing_status", "messages", ["processing_status"])
    op.add_column(
        "leads",
        sa.Column("notification_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("leads", sa.Column("notification_next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("leads", sa.Column("notification_error", sa.String(255)))
    op.add_column("lead_feedback", sa.Column("bot_update_id", sa.BigInteger()))
    op.create_unique_constraint(
        "uq_lead_feedback_bot_update_id", "lead_feedback", ["bot_update_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_lead_feedback_bot_update_id", "lead_feedback", type_="unique"
    )
    op.drop_column("lead_feedback", "bot_update_id")
    op.drop_column("leads", "notification_error")
    op.drop_column("leads", "notification_next_attempt_at")
    op.drop_column("leads", "notification_attempts")
    op.drop_index("ix_messages_processing_status", table_name="messages")
    op.drop_column("messages", "processing_error")
    op.drop_column("messages", "processing_next_attempt_at")
    op.drop_column("messages", "processing_attempts")
    op.drop_column("messages", "processing_status")
