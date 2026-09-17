"""Add discovery queries and search profiles."""

from alembic import op
import sqlalchemy as sa

revision = "0004_discovery_profiles"
down_revision = "0003_processing_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("categories", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("positive_keywords", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("negative_keywords", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("min_score", sa.Integer(), server_default="70", nullable=False),
        sa.Column("include_vacancies", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "notification_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_profiles_enabled", "search_profiles", ["enabled"])
    op.create_table(
        "discovery_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("query", sa.String(255), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_discovery_queries_enabled", "discovery_queries", ["enabled"])
    op.add_column("messages", sa.Column("matched_profile_id", sa.Integer()))
    op.create_foreign_key(
        "fk_messages_matched_profile",
        "messages",
        "search_profiles",
        ["matched_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("leads", sa.Column("search_profile_id", sa.Integer()))
    op.create_foreign_key(
        "fk_leads_search_profile",
        "leads",
        "search_profiles",
        ["search_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_leads_search_profile", "leads", type_="foreignkey")
    op.drop_column("leads", "search_profile_id")
    op.drop_constraint("fk_messages_matched_profile", "messages", type_="foreignkey")
    op.drop_column("messages", "matched_profile_id")
    op.drop_index("ix_discovery_queries_enabled", table_name="discovery_queries")
    op.drop_table("discovery_queries")
    op.drop_index("ix_search_profiles_enabled", table_name="search_profiles")
    op.drop_table("search_profiles")
