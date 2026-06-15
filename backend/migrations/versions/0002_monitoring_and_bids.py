"""monitoring, bid workflow, notifications

Adds tender_sources, discovered_tenders, bids, bid_events, notifications.

Revision ID: 0002_monitoring_and_bids
Revises: 0001_initial
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from app.db_types import GUID, JSONB, ARRAY

revision = "0002_monitoring_and_bids"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tender_sources",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), default="sample"),
        sa.Column("url", sa.String(1024)),
        sa.Column("config", JSONB()),
        sa.Column("keywords", ARRAY(sa.String())),
        sa.Column("sectors", ARRAY(sa.String())),
        sa.Column("states", ARRAY(sa.String())),
        sa.Column("min_value", sa.Numeric(15, 2)),
        sa.Column("max_value", sa.Numeric(15, 2)),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_checked_at", sa.DateTime()),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "discovered_tenders",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_id", GUID(), sa.ForeignKey("tender_sources.id"), nullable=False),
        sa.Column("external_id", sa.String(512), nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("tender_value", sa.Numeric(15, 2)),
        sa.Column("bid_deadline", sa.DateTime()),
        sa.Column("sector", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("url", sa.String(1024)),
        sa.Column("match_score", sa.Float(), default=0.0),
        sa.Column("match_reasons", JSONB()),
        sa.Column("status", sa.String(50), default="new"),
        sa.Column("discovered_at", sa.DateTime()),
    )
    op.create_index(
        "ix_discovered_source_external", "discovered_tenders",
        ["source_id", "external_id"], unique=True,
    )
    op.create_index("ix_discovered_org_status", "discovered_tenders", ["organization_id", "status"])

    op.create_table(
        "bids",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("tender_id", GUID(), sa.ForeignKey("tenders.id")),
        sa.Column("discovered_tender_id", GUID(), sa.ForeignKey("discovered_tenders.id")),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("stage", sa.String(50), default="identified"),
        sa.Column("assigned_to_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("created_by_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("tender_value", sa.Numeric(15, 2)),
        sa.Column("bid_deadline", sa.DateTime()),
        sa.Column("win_probability", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.Column("deadline_alerts_sent", JSONB()),
        sa.Column("decided_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_bids_org_stage", "bids", ["organization_id", "stage"])

    op.create_table(
        "bid_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("bid_id", GUID(), sa.ForeignKey("bids.id"), nullable=False),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_value", sa.String(255)),
        sa.Column("to_value", sa.String(255)),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_bid_events_bid", "bid_events", ["bid_id"])

    op.create_table(
        "notifications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("link", sa.String(1024)),
        sa.Column("bid_id", GUID(), sa.ForeignKey("bids.id")),
        sa.Column("discovered_tender_id", GUID(), sa.ForeignKey("discovered_tenders.id")),
        sa.Column("dedup_key", sa.String(512)),
        sa.Column("is_read", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_notifications_org_user", "notifications", ["organization_id", "user_id"])
    op.create_index("ix_notifications_dedup", "notifications", ["organization_id", "dedup_key"])


def downgrade():
    for table in (
        "notifications", "bid_events", "bids",
        "discovered_tenders", "tender_sources",
    ):
        op.drop_table(table)
