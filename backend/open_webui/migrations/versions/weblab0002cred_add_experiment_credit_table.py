"""Add experiment_credit table for credit tracking

Revision ID: weblab0002cred
Revises: weblab0001exp
Create Date: 2026-03-04 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "weblab0002cred"
down_revision: Union[str, None] = "weblab0001exp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_credit",
        sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
        sa.Column(
            "experiment_id",
            sa.Text(),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "event_id",
            sa.Text(),
            sa.ForeignKey("experiment_event.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("exp_credit_experiment_idx", "experiment_credit", ["experiment_id"])
    op.create_index("exp_credit_user_idx", "experiment_credit", ["user_id"])
    op.create_index("exp_credit_type_idx", "experiment_credit", ["type"])
    op.create_index(
        "exp_credit_exp_user_idx",
        "experiment_credit",
        ["experiment_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("exp_credit_exp_user_idx", table_name="experiment_credit")
    op.drop_index("exp_credit_type_idx", table_name="experiment_credit")
    op.drop_index("exp_credit_user_idx", table_name="experiment_credit")
    op.drop_index("exp_credit_experiment_idx", table_name="experiment_credit")
    op.drop_table("experiment_credit")
