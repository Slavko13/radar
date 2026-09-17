"""Add encrypted Telegram account session references."""

from alembic import op
import sqlalchemy as sa

revision = "0002_telegram_accounts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("telegram_user_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("account_name", sa.String(255)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("session_reference", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("telegram_accounts")
