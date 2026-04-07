"""MRR metric tables."""

from sqlalchemy import BigInteger, Column, DateTime, Table, Text, UniqueConstraint

from tidemill.models import metadata

metric_mrr_snapshot = Table(
    "metric_mrr_snapshot",
    metadata,
    Column("id", Text, primary_key=True),
    Column("source_id", Text, nullable=False),
    Column("customer_id", Text, nullable=False),
    Column("subscription_id", Text, nullable=False),
    Column("mrr_cents", BigInteger, nullable=False),
    Column("mrr_base_cents", BigInteger, nullable=False),
    Column("currency", Text, nullable=False),
    Column("snapshot_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", "subscription_id", name="uq_mrr_snapshot_sub"),
)

metric_mrr_movement = Table(
    "metric_mrr_movement",
    metadata,
    Column("id", Text, primary_key=True),
    Column("event_id", Text, nullable=False, unique=True),
    Column("source_id", Text, nullable=False),
    Column("customer_id", Text, nullable=False),
    Column("subscription_id", Text, nullable=False),
    Column("movement_type", Text, nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    Column("amount_base_cents", BigInteger, nullable=False),
    Column("currency", Text, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
)
