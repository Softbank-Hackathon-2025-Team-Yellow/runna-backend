"""Add deployment tracking fields to Function model

Revision ID: a8f3c29d4e51
Revises: fc1bd85cede5
Create Date: 2025-12-05 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f3c29d4e51'
down_revision: Union[str, None] = 'fc1bd85cede5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create DeploymentStatus enum type
    deployment_status_enum = sa.Enum(
        'NOT_DEPLOYED', 
        'DEPLOYING', 
        'DEPLOYED', 
        'FAILED',
        name='deploymentstatus'
    )
    deployment_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Add deployment tracking columns to functions table
    op.add_column('functions', sa.Column('deployment_status', sa.Enum('NOT_DEPLOYED', 'DEPLOYING', 'DEPLOYED', 'FAILED', name='deploymentstatus'), nullable=False, server_default='NOT_DEPLOYED'))
    op.add_column('functions', sa.Column('knative_url', sa.String(length=500), nullable=True))
    op.add_column('functions', sa.Column('last_deployed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('functions', sa.Column('deployment_error', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove deployment tracking columns
    op.drop_column('functions', 'deployment_error')
    op.drop_column('functions', 'last_deployed_at')
    op.drop_column('functions', 'knative_url')
    op.drop_column('functions', 'deployment_status')
    
    # Drop DeploymentStatus enum type
    deployment_status_enum = sa.Enum(
        'NOT_DEPLOYED', 
        'DEPLOYING', 
        'DEPLOYED', 
        'FAILED',
        name='deploymentstatus'
    )
    deployment_status_enum.drop(op.get_bind(), checkfirst=True)
