"""Add configurable retention for processed non-lead messages."""

import sqlalchemy as sa

from alembic import op

revision = "0009_message_retention"
down_revision = "0008_quality_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    settings_columns = {
        column["name"] for column in inspector.get_columns("app_settings")
    }
    if "message_retention_days" not in settings_columns:
        op.add_column(
            "app_settings",
            sa.Column(
                "message_retention_days",
                sa.Integer(),
                nullable=False,
                server_default="14",
            ),
        )


def downgrade() -> None:
    op.drop_column("app_settings", "message_retention_days")
