"""initial schema — all core tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from app.db_types import GUID, JSONB, ARRAY

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("domain", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("max_monthly_analyses", sa.Integer(), default=10),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), default="member"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_login", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_org_id", "users", ["organization_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("razorpay_subscription_id", sa.String(255)),
        sa.Column("razorpay_customer_id", sa.String(255)),
        sa.Column("tier", sa.String(50), default="free"),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("price_per_month", sa.Numeric(10, 2), default=0),
        sa.Column("current_cycle_start", sa.DateTime()),
        sa.Column("current_cycle_end", sa.DateTime()),
        sa.Column("next_billing_date", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "company_profiles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("annual_turnover", sa.Numeric(12, 2)),
        sa.Column("net_worth", sa.Numeric(12, 2)),
        sa.Column("team_size", sa.Integer(), default=0),
        sa.Column("sectors", ARRAY(sa.String)),
        sa.Column("operating_states", ARRAY(sa.String)),
        sa.Column("certifications", JSONB()),
        sa.Column("registrations", JSONB()),
        sa.Column("years_in_business", sa.Integer(), default=0),
        sa.Column("past_projects", JSONB()),
        sa.Column("bid_success_rate", sa.Float(), default=0.5),
        sa.Column("liquid_assets", sa.Numeric(12, 2)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "tenders",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("company_profile_id", GUID(), sa.ForeignKey("company_profiles.id")),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(255)),
        sa.Column("page_count", sa.Integer()),
        sa.Column("is_scanned", sa.Boolean(), default=False),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("job_id", sa.String(255)),
        sa.Column("processed_at", sa.DateTime()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_tenders_org_id", "tenders", ["organization_id"])
    op.create_index("ix_tenders_status", "tenders", ["status"])

    op.create_table(
        "tender_analyses",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tender_id", GUID(), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("tender_value", sa.Numeric(15, 2)),
        sa.Column("bid_deadline", sa.DateTime()),
        sa.Column("sector", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("eligibility_criteria", JSONB()),
        sa.Column("required_documents", JSONB()),
        sa.Column("penalty_clauses", JSONB()),
        sa.Column("key_dates", JSONB()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "tender_scores",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tender_id", GUID(), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("company_profile_id", GUID(), sa.ForeignKey("company_profiles.id"), nullable=False),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("win_probability", sa.Float(), default=0.0),
        sa.Column("eligibility_score", sa.Float(), default=0.0),
        sa.Column("fit_score", sa.Float(), default=0.0),
        sa.Column("risk_level", sa.String(50), default="medium"),
        sa.Column("risk_score", sa.Float(), default=0.0),
        sa.Column("competition_intensity", sa.String(50), default="medium"),
        sa.Column("recommendation", sa.String(50), default="skip"),
        sa.Column("factors", JSONB()),
        sa.Column("reasoning", JSONB()),
        sa.Column("user_feedback", sa.String(50)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "usage_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("tenders_analyzed", sa.Integer(), default=0),
        sa.Column("api_calls", sa.Integer(), default=0),
        sa.Column("storage_used_mb", sa.Float(), default=0),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_usage_org_month", "usage_logs", ["organization_id", "month"])

    op.create_table(
        "api_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade():
    for table in (
        "api_logs", "usage_logs", "tender_scores", "tender_analyses",
        "tenders", "company_profiles", "subscriptions", "users", "organizations",
    ):
        op.drop_table(table)
