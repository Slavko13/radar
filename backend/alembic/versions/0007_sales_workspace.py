"""Add portfolio, workflow and notification settings."""

import sqlalchemy as sa
from alembic import op

revision = "0007_sales_workspace"
down_revision = "0006_actionable_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column(
        "leads", sa.Column("suggested_materials", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column("leads", sa.Column("fit_score", sa.Integer()))
    op.add_column(
        "leads", sa.Column("workflow_status", sa.String(20), nullable=False, server_default="NEW")
    )
    op.add_column("leads", sa.Column("notes", sa.Text()))
    op.create_index("ix_leads_fit_score", "leads", ["fit_score"])
    op.create_index("ix_leads_workflow_status", "leads", ["workflow_status"])
    op.add_column("lead_feedback", sa.Column("reason", sa.String(50)))

    op.add_column(
        "app_settings",
        sa.Column("notification_mode", sa.String(20), nullable=False, server_default="IMMEDIATE"),
    )
    op.add_column(
        "app_settings",
        sa.Column("digest_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column("app_settings", sa.Column("last_digest_at", sa.DateTime(timezone=True)))
    op.add_column(
        "app_settings",
        sa.Column("max_lead_age_hours", sa.Integer(), nullable=False, server_default="168"),
    )
    op.add_column(
        "app_settings",
        sa.Column("require_contact", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "portfolio_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("company_name", sa.String(200)),
        sa.Column("description", sa.Text()),
        sa.Column("services", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("desired_offer_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("minimum_budget", sa.Numeric(14, 2)),
        sa.Column("budget_currency", sa.String(3)),
        sa.Column("contact_signature", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "portfolio_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("url", sa.String(500)),
        sa.Column("services", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("result", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_portfolio_items_active", "portfolio_items", ["active"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_items_active", table_name="portfolio_items")
    op.drop_table("portfolio_items")
    op.drop_table("portfolio_profiles")
    op.drop_column("app_settings", "require_contact")
    op.drop_column("app_settings", "max_lead_age_hours")
    op.drop_column("app_settings", "last_digest_at")
    op.drop_column("app_settings", "digest_interval_minutes")
    op.drop_column("app_settings", "notification_mode")
    op.drop_column("lead_feedback", "reason")
    op.drop_index("ix_leads_workflow_status", table_name="leads")
    op.drop_index("ix_leads_fit_score", table_name="leads")
    op.drop_column("leads", "notes")
    op.drop_column("leads", "workflow_status")
    op.drop_column("leads", "fit_score")
    op.drop_column("leads", "suggested_materials")
    op.drop_column("leads", "evidence")
