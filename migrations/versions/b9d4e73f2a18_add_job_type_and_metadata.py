"""Add job_type and metadata to Job model

Revision ID: b9d4e73f2a18
Revises: a8f3c29d4e51
Create Date: 2025-12-05 22:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9d4e73f2a18'
down_revision: Union[str, None] = 'a8f3c29d4e51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create JobType enum type
    job_type_enum = sa.Enum(
        'EXECUTION', 
        'DEPLOYMENT',
        name='jobtype'
    )
    job_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Add job_type column to jobs table
    op.add_column('jobs', sa.Column('job_type', sa.Enum('EXECUTION', 'DEPLOYMENT', name='jobtype'), nullable=False, server_default='EXECUTION'))


def downgrade() -> None:
    # Remove job_type column
    op.drop_column('jobs', 'job_type')
    
    # Drop JobType enum type
    job_type_enum = sa.Enum(
        'EXECUTION', 
        'DEPLOYMENT',
        name='jobtype'
    )
    job_type_enum.drop(op.get_bind(), checkfirst=True)
