"""Add user_postponement table for explicit postponement tracking

Revision ID: weblab0003post
Revises: weblab0002cred
Create Date: 2026-03-04 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "weblab0003post"
down_revision: Union[str, None] = "weblab0002cred"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_postponement",
        sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
        sa.Column(
            "experiment_id",
            sa.Text(),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("ends_at", sa.BigInteger(), nullable=False),
        sa.Column(
            "credit_amount",
            sa.Float(),
            nullable=False,
            server_default="1.0",
        ),
        sa.Column(
            "credit_id",
            sa.Text(),
            sa.ForeignKey("experiment_credit.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
        ),  # active, completed, overridden
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "user_postponement_exp_user_idx",
        "user_postponement",
        ["experiment_id", "user_id"],
    )
    op.create_index(
        "user_postponement_status_idx",
        "user_postponement",
        ["status"],
    )
    op.create_index(
        "user_postponement_ends_at_idx",
        "user_postponement",
        ["ends_at"],
    )


def downgrade() -> None:
    op.drop_index("user_postponement_ends_at_idx", table_name="user_postponement")
    op.drop_index("user_postponement_status_idx", table_name="user_postponement")
    op.drop_index("user_postponement_exp_user_idx", table_name="user_postponement")
    op.drop_table("user_postponement")
