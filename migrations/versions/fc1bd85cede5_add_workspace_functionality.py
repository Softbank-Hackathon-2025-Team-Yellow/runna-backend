"""add workspace functionality

Revision ID: fc1bd85cede5
Revises: 4c7bbae0476b
Create Date: 2025-12-03 09:52:53.062248

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc1bd85cede5"
down_revision: Union[str, Sequence[str], None] = "4c7bbae0476b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspaces_id"), "workspaces", ["id"], unique=False)
    op.create_index(op.f("ix_workspaces_name"), "workspaces", ["name"], unique=True)

    # Add workspace_id column as nullable first
    op.add_column("functions", sa.Column("workspace_id", sa.UUID(), nullable=True))

    # Data migration: Create default workspaces for existing users and update functions
    connection = op.get_bind()

    # Get all users
    users_result = connection.execute(sa.text("SELECT id FROM users"))
    users = users_result.fetchall()

    if users:
        # For each user, create a default workspace
        workspace_mapping = {}
        for i, user_row in enumerate(users):
            user_id = user_row[0]
            workspace_id = str(uuid.uuid4())
            workspace_mapping[user_id] = workspace_id

            # Create unique workspace name for each user
            workspace_name = f"Default Workspace (User {user_id})"

            connection.execute(
                sa.text(
                    """
                INSERT INTO workspaces (id, name, user_id, created_at, updated_at)
                VALUES (:id, :name, :user_id, NOW(), NOW())
            """
                ),
                {"id": workspace_id, "name": workspace_name, "user_id": user_id},
            )

        # Get all functions and assign them to their user's default workspace
        functions_result = connection.execute(
            sa.text(
                """
            SELECT f.id, u.id as user_id
            FROM functions f
            JOIN users u ON 1=1  -- Cross join to assign to first user for functions without clear ownership
            LIMIT (SELECT COUNT(*) FROM functions)
        """
            )
        )
        functions = functions_result.fetchall()

        if functions:
            # For simplicity, assign all functions to the first user's workspace
            # In a real scenario, you might have a way to determine function ownership
            if users:
                first_user_id = users[0][0]
                default_workspace_id = workspace_mapping[first_user_id]

                connection.execute(
                    sa.text(
                        """
                    UPDATE functions
                    SET workspace_id = :workspace_id
                """
                    ),
                    {"workspace_id": default_workspace_id},
                )

    # Now make workspace_id NOT NULL and add foreign key constraint
    op.alter_column("functions", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_functions_workspace_id", "functions", "workspaces", ["workspace_id"], ["id"]
    )
    op.create_index(
        op.f("ix_functions_workspace_id"), "functions", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop function workspace relationship
    op.drop_index(op.f("ix_functions_workspace_id"), table_name="functions")
    op.drop_constraint("fk_functions_workspace_id", "functions", type_="foreignkey")
    op.drop_column("functions", "workspace_id")

    # Drop workspaces table
    op.drop_index(op.f("ix_workspaces_name"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_id"), table_name="workspaces")
    op.drop_table("workspaces")
