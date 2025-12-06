"""add unique constraint for function name per workspace

Revision ID: 20251207_func_name
Revises: f9826bb69d03
Create Date: 2025-12-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251207_func_name'
down_revision: Union[str, Sequence[str], None] = 'f9826bb69d03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint for (workspace_id, name) on functions table."""
    # Create unique constraint for function name within workspace
    op.create_unique_constraint(
        'uq_workspace_name',  # constraint name
        'functions',  # table name
        ['workspace_id', 'name']  # columns
    )


def downgrade() -> None:
    """Remove unique constraint for (workspace_id, name) on functions table."""
    # Drop the unique constraint
    op.drop_constraint('uq_workspace_name', 'functions', type_='unique')
