"""add_workspace_alias_and_function_endpoint

Revision ID: f9826bb69d03
Revises: fc1bd85cede5
Create Date: 2025-12-04 23:37:41.434178

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9826bb69d03'
down_revision: Union[str, Sequence[str], None] = 'fc1bd85cede5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Workspace alias 및 Function endpoint 필드 추가

    - Workspace.alias: 불변 식별자 (subdomain/namespace 연결용)
    - Function.endpoint: 커스텀 가능한 URL 경로
    """
    # Workspace에 alias 컬럼 추가
    op.add_column('workspaces', sa.Column('alias', sa.String(length=20), nullable=False))
    op.create_unique_constraint('uq_workspaces_alias', 'workspaces', ['alias'])
    op.create_index('ix_workspaces_alias', 'workspaces', ['alias'], unique=True)

    # Function에 endpoint 컬럼 추가
    op.add_column('functions', sa.Column('endpoint', sa.String(length=100), nullable=False))
    op.create_unique_constraint('uq_functions_endpoint', 'functions', ['endpoint'])
    op.create_index('ix_functions_endpoint', 'functions', ['endpoint'], unique=True)


def downgrade() -> None:
    """Rollback schema changes."""
    # Function endpoint 컬럼 제거
    op.drop_index('ix_functions_endpoint', table_name='functions')
    op.drop_constraint('uq_functions_endpoint', 'functions', type_='unique')
    op.drop_column('functions', 'endpoint')

    # Workspace alias 컬럼 제거
    op.drop_index('ix_workspaces_alias', table_name='workspaces')
    op.drop_constraint('uq_workspaces_alias', 'workspaces', type_='unique')
    op.drop_column('workspaces', 'alias')
