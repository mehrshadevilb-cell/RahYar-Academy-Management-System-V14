"""add moderated project marketplace

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("student_profiles", sa.Column("skills", sa.Text(), nullable=False, server_default=""))
    op.create_table(
        "marketplace_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("employer_name", sa.String(length=120), nullable=False),
        sa.Column("employer_contact", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("skills", sa.Text(), nullable=False, server_default=""),
        sa.Column("budget_min", sa.Integer(), nullable=True),
        sa.Column("budget_max", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.String(length=80), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.Enum("PENDING_REVIEW", "PUBLISHED", "REJECTED", "CLOSED", name="projectstatus"), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_marketplace_projects_id", "marketplace_projects", ["id"])
    op.create_index("ix_marketplace_projects_employer_user_id", "marketplace_projects", ["employer_user_id"])
    op.create_index("ix_marketplace_projects_category", "marketplace_projects", ["category"])
    op.create_index("ix_marketplace_projects_status", "marketplace_projects", ["status"])
    op.create_table(
        "marketplace_project_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("marketplace_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cover_letter", sa.Text(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("SUBMITTED", "SHORTLISTED", "ACCEPTED", "DECLINED", "WITHDRAWN", name="applicationstatus"), nullable=False, server_default="SUBMITTED"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_marketplace_project_applications_id", "marketplace_project_applications", ["id"])
    op.create_index("ix_marketplace_project_applications_project_id", "marketplace_project_applications", ["project_id"])
    op.create_index("ix_marketplace_project_applications_student_user_id", "marketplace_project_applications", ["student_user_id"])
    op.create_index("ix_marketplace_project_applications_status", "marketplace_project_applications", ["status"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_project_applications_status", table_name="marketplace_project_applications")
    op.drop_index("ix_marketplace_project_applications_student_user_id", table_name="marketplace_project_applications")
    op.drop_index("ix_marketplace_project_applications_project_id", table_name="marketplace_project_applications")
    op.drop_index("ix_marketplace_project_applications_id", table_name="marketplace_project_applications")
    op.drop_table("marketplace_project_applications")
    op.drop_index("ix_marketplace_projects_status", table_name="marketplace_projects")
    op.drop_index("ix_marketplace_projects_category", table_name="marketplace_projects")
    op.drop_index("ix_marketplace_projects_employer_user_id", table_name="marketplace_projects")
    op.drop_index("ix_marketplace_projects_id", table_name="marketplace_projects")
    op.drop_table("marketplace_projects")
    op.drop_column("student_profiles", "skills")
    sa.Enum(name="applicationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="projectstatus").drop(op.get_bind(), checkfirst=True)
