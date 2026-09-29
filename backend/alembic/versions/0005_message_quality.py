"""Add message similarity and suppression metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0005_message_quality"
down_revision = "0004_discovery_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("content_fingerprint", sa.String(64)))
    op.add_column("messages", sa.Column("duplicate_of_message_id", sa.Integer()))
    op.add_column("messages", sa.Column("suppression_reason", sa.String(50)))
    op.create_index(
        "ix_messages_content_fingerprint", "messages", ["content_fingerprint"]
    )
    op.create_foreign_key(
        "fk_messages_duplicate_of",
        "messages",
        "messages",
        ["duplicate_of_message_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_duplicate_of", "messages", type_="foreignkey")
    op.drop_index("ix_messages_content_fingerprint", table_name="messages")
    op.drop_column("messages", "suppression_reason")
    op.drop_column("messages", "duplicate_of_message_id")
    op.drop_column("messages", "content_fingerprint")
