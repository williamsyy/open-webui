"""Add experiment tables for web lab system

Revision ID: weblab0001exp
Revises: f0bd01a18a3d
Create Date: 2026-03-04 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "weblab0001exp"
down_revision: Union[str, None] = "f0bd01a18a3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create experiment table
    op.create_table(
        "experiment",
        sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("start_date", sa.BigInteger(), nullable=True),
        sa.Column("end_date", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )

    # 2. Create experiment_group table
    op.create_table(
        "experiment_group",
        sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
        sa.Column(
            "experiment_id",
            sa.Text(),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_experiment_group_experiment_id",
        "experiment_group",
        ["experiment_id"],
    )

    # 3. Create experiment_assignment table
    op.create_table(
        "experiment_assignment",
        sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
        sa.Column(
            "experiment_id",
            sa.Text(),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.Text(),
            sa.ForeignKey("experiment_group.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("assigned_at", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by", sa.Text(), nullable=True),
    )
    op.create_index(
        "exp_assignment_experiment_idx",
        "experiment_assignment",
        ["experiment_id"],
    )
    op.create_index(
        "exp_assignment_user_idx",
        "experiment_assignment",
        ["user_id"],
    )
    op.create_index(
        "exp_assignment_group_idx",
        "experiment_assignment",
        ["group_id"],
    )
    op.create_index(
        "exp_assignment_exp_user_idx",
        "experiment_assignment",
        ["experiment_id", "user_id"],
        unique=True,
    )

    # 4. Create experiment_event table
    op.create_table(
        "experiment_event",
        sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
        sa.Column(
            "experiment_id",
            sa.Text(),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.Text(),
            sa.ForeignKey("experiment_group.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "exp_event_experiment_idx",
        "experiment_event",
        ["experiment_id"],
    )
    op.create_index(
        "exp_event_user_idx",
        "experiment_event",
        ["user_id"],
    )
    op.create_index(
        "exp_event_type_idx",
        "experiment_event",
        ["event_type"],
    )
    op.create_index(
        "exp_event_created_idx",
        "experiment_event",
        ["created_at"],
    )

    # 5. Create experiment_usage_snapshot table
    op.create_table(
        "experiment_usage_snapshot",
        sa.Column("id", sa.Text(), primary_key=True, unique=True, nullable=False),
        sa.Column(
            "experiment_id",
            sa.Text(),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.Text(),
            sa.ForeignKey("experiment_group.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Text(), nullable=False),
        sa.Column("total_messages", sa.Integer(), server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), server_default="0"),
        sa.Column("active_users", sa.Integer(), server_default="0"),
        sa.Column("interventions_shown", sa.Integer(), server_default="0"),
        sa.Column("interventions_accepted", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "exp_snapshot_experiment_idx",
        "experiment_usage_snapshot",
        ["experiment_id"],
    )
    op.create_index(
        "exp_snapshot_date_idx",
        "experiment_usage_snapshot",
        ["snapshot_date"],
    )
    op.create_index(
        "exp_snapshot_exp_group_date_idx",
        "experiment_usage_snapshot",
        ["experiment_id", "group_id", "snapshot_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("experiment_usage_snapshot")
    op.drop_table("experiment_event")
    op.drop_table("experiment_assignment")
    op.drop_table("experiment_group")
    op.drop_table("experiment")
