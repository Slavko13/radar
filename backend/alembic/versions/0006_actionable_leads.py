"""Add actionable offer and contact fields to leads."""

import sqlalchemy as sa
from alembic import op

revision = "0006_actionable_leads"
down_revision = "0005_message_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("title", sa.String(200)))
    op.add_column(
        "leads", sa.Column("offer_type", sa.String(30), nullable=False, server_default="UNKNOWN")
    )
    op.add_column("leads", sa.Column("requirements", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("leads", sa.Column("work_format", sa.String(100)))
    op.add_column("leads", sa.Column("contact_type", sa.String(30)))
    op.add_column("leads", sa.Column("contact_value", sa.String(255)))
    op.add_column("leads", sa.Column("contact_url", sa.String(500)))
    op.add_column("leads", sa.Column("contact_source", sa.String(30)))
    op.add_column("leads", sa.Column("contact_confidence", sa.Float()))
    op.create_index("ix_leads_offer_type", "leads", ["offer_type"])


def downgrade() -> None:
    op.drop_index("ix_leads_offer_type", table_name="leads")
    op.drop_column("leads", "contact_confidence")
    op.drop_column("leads", "contact_source")
    op.drop_column("leads", "contact_url")
    op.drop_column("leads", "contact_value")
    op.drop_column("leads", "contact_type")
    op.drop_column("leads", "work_format")
    op.drop_column("leads", "requirements")
    op.drop_column("leads", "offer_type")
    op.drop_column("leads", "title")
