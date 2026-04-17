"""Trials metric tables."""

from sqlalchemy import Column, DateTime, Table, Text, UniqueConstraint

from tidemill.models import metadata

metric_trial_event = Table(
    "metric_trial_event",
    metadata,
    Column("id", Text, primary_key=True),
    Column("event_id", Text, nullable=False, unique=True),
    Column("source_id", Text, nullable=False),
    Column("customer_id", Text, nullable=False),
    Column("subscription_id", Text, nullable=False),
    Column("event_type", Text, nullable=False),  # started | converted | expired
    Column("occurred_at", DateTime(timezone=True), nullable=False),
)

# One row per trial (= per subscription that entered trialing).  The
# cohort-based queries aggregate over this table: a trial belongs to the
# period of its ``started_at`` regardless of when it converts or expires.
metric_trial = Table(
    "metric_trial",
    metadata,
    Column("id", Text, primary_key=True),
    Column("source_id", Text, nullable=False),
    Column("customer_id", Text, nullable=False),
    Column("subscription_id", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("converted_at", DateTime(timezone=True)),
    Column("expired_at", DateTime(timezone=True)),
    UniqueConstraint("source_id", "subscription_id", name="uq_trial_sub"),
)
