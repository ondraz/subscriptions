"""Retention metric tables."""

from sqlalchemy import Column, Date, Table, Text, UniqueConstraint

from tidemill.models import metadata

metric_retention_cohort = Table(
    "metric_retention_cohort",
    metadata,
    Column("id", Text, primary_key=True),
    Column("source_id", Text, nullable=False),
    Column("customer_id", Text, nullable=False),
    Column("cohort_month", Date, nullable=False),
    UniqueConstraint("source_id", "customer_id", name="uq_retention_cohort_customer"),
)

metric_retention_activity = Table(
    "metric_retention_activity",
    metadata,
    Column("id", Text, primary_key=True),
    Column("source_id", Text, nullable=False),
    Column("customer_id", Text, nullable=False),
    Column("active_month", Date, nullable=False),
    UniqueConstraint(
        "source_id",
        "customer_id",
        "active_month",
        name="uq_retention_activity",
    ),
)
