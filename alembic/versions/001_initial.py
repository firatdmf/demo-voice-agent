"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2026-03-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # packages
    op.create_table(
        "packages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("package_id", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("delivery", sa.String(20), nullable=False),
        sa.Column("platform", sa.String(100)),
        sa.Column("team_required", sa.Boolean, default=False),
        sa.Column("teams_supported", JSON, default=[]),
        sa.Column("notes", JSON, default=[]),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_packages_package_id", "packages", ["package_id"])

    # package_pricing
    op.create_table(
        "package_pricing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("package_id", UUID(as_uuid=True), sa.ForeignKey("packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_type", sa.String(50), nullable=False),
        sa.Column("amount_monthly", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), default="TRY"),
    )

    # customers
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("surname", sa.String(100), nullable=False),
        sa.Column("tckn", sa.String(256)),
        sa.Column("birth_date", sa.Date),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("city", sa.String(100)),
        sa.Column("district", sa.String(100)),
        sa.Column("neighborhood", sa.String(100)),
        sa.Column("street", sa.String(200)),
        sa.Column("building_no", sa.String(20)),
        sa.Column("apartment_no", sa.String(20)),
        sa.Column("address_freeform", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # applications
    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("package_id", UUID(as_uuid=True), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("team", sa.String(100)),
        sa.Column("payment_type", sa.String(50), nullable=False),
        sa.Column("delivery", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("apply_token", sa.String(256)),
        sa.Column("apply_url", sa.String(500)),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # call_sessions
    op.create_table(
        "call_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("twilio_call_sid", sa.String(100), unique=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("caller_phone", sa.String(20)),
        sa.Column("state_history", JSON, default=[]),
        sa.Column("conversation_summary", sa.Text),
        sa.Column("flags", JSON, default=[]),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), default="active"),
    )
    op.create_index("ix_call_sessions_twilio_call_sid", "call_sessions", ["twilio_call_sid"])

    # sms_logs
    op.create_table(
        "sms_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("to_phone", sa.String(20), nullable=False),
        sa.Column("template", sa.String(100)),
        sa.Column("message_body", sa.Text),
        sa.Column("status", sa.String(20), default="sent"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("sms_logs")
    op.drop_table("call_sessions")
    op.drop_table("applications")
    op.drop_table("customers")
    op.drop_table("package_pricing")
    op.drop_table("packages")
