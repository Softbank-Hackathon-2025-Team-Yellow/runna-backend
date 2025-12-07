"""add_api_key_to_workspace

Revision ID: ffbc949cb333
Revises: 20251207_func_name
Create Date: 2025-12-07 02:03:58.330995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision: str = 'ffbc949cb333'
down_revision: Union[str, Sequence[str], None] = '20251207_func_name'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add api_key to workspaces table."""
    # Add api_key column to workspaces table
    op.add_column(
        'workspaces',
        sa.Column(
            'api_key',
            postgresql.UUID(as_uuid=True),
            nullable=True,
            unique=True,
        )
    )
    
    # Create index for api_key
    op.create_index('ix_workspaces_api_key', 'workspaces', ['api_key'], unique=True)
    
    # Update existing workspaces with new api_keys
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT id FROM workspaces"))
    for row in result:
        new_api_key = str(uuid.uuid4())
        connection.execute(
            sa.text("UPDATE workspaces SET api_key = :api_key WHERE id = :workspace_id"),
            {"api_key": new_api_key, "workspace_id": str(row[0])}
        )
    
    # Make api_key column NOT NULL after populating existing records
    op.alter_column(
        'workspaces',
        'api_key',
        nullable=False
    )


def downgrade() -> None:
    """Downgrade schema - Remove api_key from workspaces table."""
    # Drop index
    op.drop_index('ix_workspaces_api_key', table_name='workspaces')
    
    # Remove api_key column from workspaces table
    op.drop_column('workspaces', 'api_key')
