"""Add AI versioning and scheduled discovery settings."""

import sqlalchemy as sa
from alembic import op

revision = "0008_quality_automation"
down_revision = "0007_sales_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    lead_columns = {column["name"] for column in inspector.get_columns("leads")}
    settings_columns = {
        column["name"] for column in inspector.get_columns("app_settings")
    }
    if "classification_version" not in lead_columns:
        op.add_column("leads", sa.Column("classification_version", sa.String(50)))
    if "automatic_discovery" not in settings_columns:
        op.add_column(
            "app_settings",
            sa.Column(
                "automatic_discovery",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "discovery_interval_hours" not in settings_columns:
        op.add_column(
            "app_settings",
            sa.Column(
                "discovery_interval_hours",
                sa.Integer(),
                nullable=False,
                server_default="24",
            ),
        )


def downgrade() -> None:
    op.drop_column("app_settings", "discovery_interval_hours")
    op.drop_column("app_settings", "automatic_discovery")
    op.drop_column("leads", "classification_version")
