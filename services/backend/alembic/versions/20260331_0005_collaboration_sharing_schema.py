"""create collaboration and sharing schema

Revision ID: 20260331_0005
Revises: 20260327_0004
Create Date: 2026-03-31 14:50:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260331_0005"
down_revision: Union[str, None] = "20260327_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workflows_owner_id", "workflows", ["owner_id"], unique=False)
    op.create_index("ix_workflows_is_public", "workflows", ["is_public"], unique=False)
    op.create_index("ix_workflows_created_at", "workflows", ["created_at"], unique=False)

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_workflow_version"),
    )
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"], unique=False)
    op.create_index("ix_workflow_versions_version_number", "workflow_versions", ["version_number"], unique=False)

    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_teams_owner_id", "teams", ["owner_id"], unique=False)

    op.create_table(
        "team_members",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default=sa.text("'member'")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="ck_team_members_role_enum"),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"], unique=False)
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"], unique=False)

    op.create_table(
        "invitations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.BigInteger(), nullable=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=True),
        sa.Column("invited_by_id", sa.BigInteger(), nullable=False),
        sa.Column("invitee_email", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_invitations_token"),
        sa.CheckConstraint("(team_id IS NOT NULL) OR (workflow_id IS NOT NULL)", name="ck_invitations_target_not_null"),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'declined', 'expired')", name="ck_invitations_status_enum"),
    )
    op.create_index("ix_invitations_team_id", "invitations", ["team_id"], unique=False)
    op.create_index("ix_invitations_workflow_id", "invitations", ["workflow_id"], unique=False)
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=False)
    op.create_index("ix_invitations_status", "invitations", ["status"], unique=False)

    op.create_table(
        "delegations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("delegator_id", sa.BigInteger(), nullable=False),
        sa.Column("delegate_id", sa.BigInteger(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegate_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("delegator_id <> delegate_id", name="ck_delegations_no_self_delegate"),
    )
    op.create_index("ix_delegations_workflow_id", "delegations", ["workflow_id"], unique=False)
    op.create_index("ix_delegations_delegator_id", "delegations", ["delegator_id"], unique=False)
    op.create_index("ix_delegations_delegate_id", "delegations", ["delegate_id"], unique=False)

    op.create_table(
        "share_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("access_mode", sa.String(length=20), nullable=False, server_default=sa.text("'read'")),
        sa.Column("password", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_share_links_token"),
        sa.CheckConstraint("access_mode IN ('read', 'comment', 'edit')", name="ck_share_links_access_mode_enum"),
        sa.CheckConstraint("access_count >= 0", name="ck_share_links_access_count_non_negative"),
    )
    op.create_index("ix_share_links_workflow_id", "share_links", ["workflow_id"], unique=False)
    op.create_index("ix_share_links_token", "share_links", ["token"], unique=False)

    op.create_table(
        "comments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.String(length=4000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("length(content) > 0", name="ck_comments_content_not_empty"),
    )
    op.create_index("ix_comments_workflow_id", "comments", ["workflow_id"], unique=False)
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"], unique=False)
    op.create_index("ix_comments_user_id", "comments", ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.String(length=4000), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("reference_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"], unique=False)
    op.create_index("ix_notifications_type", "notifications", ["type"], unique=False)

    op.create_table(
        "collaboration_operations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("operation_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_collaboration_operations_workflow_id",
        "collaboration_operations",
        ["workflow_id"],
        unique=False,
    )
    op.create_index("ix_collaboration_operations_user_id", "collaboration_operations", ["user_id"], unique=False)
    op.create_index(
        "ix_collaboration_operations_created_at",
        "collaboration_operations",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "collaboration_cursors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("cursor_position", sa.JSON(), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workflow_id", "user_id", name="uq_collaboration_cursors_workflow_user"),
    )
    op.create_index("ix_collaboration_cursors_workflow_id", "collaboration_cursors", ["workflow_id"], unique=False)
    op.create_index("ix_collaboration_cursors_user_id", "collaboration_cursors", ["user_id"], unique=False)

    op.create_table(
        "collaboration_conflicts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("conflict_type", sa.String(length=64), nullable=False),
        sa.Column("conflict_data", sa.JSON(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_collaboration_conflicts_workflow_id", "collaboration_conflicts", ["workflow_id"], unique=False)
    op.create_index("ix_collaboration_conflicts_user_id", "collaboration_conflicts", ["user_id"], unique=False)
    op.create_index("ix_collaboration_conflicts_resolved", "collaboration_conflicts", ["resolved"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_collaboration_conflicts_resolved", table_name="collaboration_conflicts")
    op.drop_index("ix_collaboration_conflicts_user_id", table_name="collaboration_conflicts")
    op.drop_index("ix_collaboration_conflicts_workflow_id", table_name="collaboration_conflicts")
    op.drop_table("collaboration_conflicts")

    op.drop_index("ix_collaboration_cursors_user_id", table_name="collaboration_cursors")
    op.drop_index("ix_collaboration_cursors_workflow_id", table_name="collaboration_cursors")
    op.drop_table("collaboration_cursors")

    op.drop_index("ix_collaboration_operations_created_at", table_name="collaboration_operations")
    op.drop_index("ix_collaboration_operations_user_id", table_name="collaboration_operations")
    op.drop_index("ix_collaboration_operations_workflow_id", table_name="collaboration_operations")
    op.drop_table("collaboration_operations")

    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_comments_user_id", table_name="comments")
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_workflow_id", table_name="comments")
    op.drop_table("comments")

    op.drop_index("ix_share_links_token", table_name="share_links")
    op.drop_index("ix_share_links_workflow_id", table_name="share_links")
    op.drop_table("share_links")

    op.drop_index("ix_delegations_delegate_id", table_name="delegations")
    op.drop_index("ix_delegations_delegator_id", table_name="delegations")
    op.drop_index("ix_delegations_workflow_id", table_name="delegations")
    op.drop_table("delegations")

    op.drop_index("ix_invitations_status", table_name="invitations")
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_index("ix_invitations_workflow_id", table_name="invitations")
    op.drop_index("ix_invitations_team_id", table_name="invitations")
    op.drop_table("invitations")

    op.drop_index("ix_team_members_user_id", table_name="team_members")
    op.drop_index("ix_team_members_team_id", table_name="team_members")
    op.drop_table("team_members")

    op.drop_index("ix_teams_owner_id", table_name="teams")
    op.drop_table("teams")

    op.drop_index("ix_workflow_versions_version_number", table_name="workflow_versions")
    op.drop_index("ix_workflow_versions_workflow_id", table_name="workflow_versions")
    op.drop_table("workflow_versions")

    op.drop_index("ix_workflows_created_at", table_name="workflows")
    op.drop_index("ix_workflows_is_public", table_name="workflows")
    op.drop_index("ix_workflows_owner_id", table_name="workflows")
    op.drop_table("workflows")
