# Database

> Core schema, ER diagram, and rationale for PostgreSQL.
> Last updated: March 2026

## Why PostgreSQL (not ClickHouse)

ClickHouse excels at columnar analytics over billions of rows. But subscription analytics has different characteristics:

| Factor | Subscription Analytics | Implication |
|--------|----------------------|-------------|
| Data volume | Thousands-low millions of rows | PostgreSQL handles this comfortably |
| Write pattern | Frequent upserts from event processing | PostgreSQL's MVCC handles upserts natively; ClickHouse has eventual consistency with ReplacingMergeTree |
| Relationships | Deep: customer -> subscription -> invoice -> line items -> payments | PostgreSQL enforces referential integrity; ClickHouse has no foreign keys |
| Query pattern | JOINs across 4-5 tables for metric computation | PostgreSQL's query planner is built for this; ClickHouse JOINs are limited |
| Deployment | Self-hosted simplicity matters | PostgreSQL is the most widely deployed database; ClickHouse needs more operational expertise |

**Decision:** PostgreSQL as the single database. If a user later needs to feed a data warehouse, the metrics package can export to any target.

## Schema Ownership

The database has two categories of tables:

1. **Core tables** — managed by the framework. Store current state of billing entities and the event log. Defined below.
2. **Metric plugin tables** — each [metric plugin](metrics.md) owns its own tables (prefixed `metric_`). Created by the plugin's `register_tables()` method. See individual plugin docs in [Metrics](metrics.md).

This separation means adding a new metric never touches core schema.

## Entity-Relationship Diagram (Core Tables)

```mermaid
erDiagram
    connector_source ||--o{ customer : syncs
    connector_source ||--o{ plan : syncs
    connector_source ||--o{ subscription : syncs
    connector_source ||--o{ invoice : syncs
    connector_source ||--o{ payment : syncs
    connector_source ||--o{ event_log : produces

    customer ||--o{ subscription : has
    customer ||--o{ invoice : receives
    customer ||--o{ payment : makes

    plan ||--o{ subscription : defines
    plan ||--o{ plan_charge : contains

    subscription ||--o{ invoice : generates

    invoice ||--o{ invoice_line_item : contains
    invoice ||--o{ payment : settled_by

    plan_charge }o--|| billable_metric : prices

    connector_source {
        uuid id PK
        text type "stripe | lago | killbill"
        text name
        jsonb config "api keys, URLs, secrets"
        timestamptz last_synced_at
        timestamptz created_at
    }

    event_log {
        uuid id PK
        uuid source_id FK
        text type "subscription.created, etc"
        text customer_id "partition key"
        jsonb payload
        timestamptz occurred_at
        timestamptz published_at
    }

    customer {
        uuid id PK
        uuid source_id FK
        text external_id "ID in billing system"
        text name
        text email
        text currency "ISO 4217"
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }

    plan {
        uuid id PK
        uuid source_id FK
        text external_id
        text name
        text interval "month | year | week | quarter"
        bigint amount_cents
        text currency
        int trial_period_days
        jsonb metadata
        boolean active
        timestamptz created_at
    }

    plan_charge {
        uuid id PK
        uuid plan_id FK
        uuid billable_metric_id FK
        text charge_model "standard | tiered | volume | package | percentage"
        jsonb properties "tiers, rates, etc"
        timestamptz created_at
    }

    billable_metric {
        uuid id PK
        uuid source_id FK
        text code "api_calls | storage_gb | tokens"
        text name
        text aggregation_type "count | sum | max | unique_count"
        text field_name "property to aggregate"
        timestamptz created_at
    }

    subscription {
        uuid id PK
        uuid source_id FK
        text external_id
        uuid customer_id FK
        uuid plan_id FK
        text status "active | canceled | past_due | trialing | paused"
        bigint mrr_cents "current MRR contribution"
        int quantity
        timestamptz started_at
        timestamptz trial_start
        timestamptz trial_end
        timestamptz canceled_at
        timestamptz ended_at
        timestamptz current_period_start
        timestamptz current_period_end
        timestamptz created_at
        timestamptz updated_at
    }

    invoice {
        uuid id PK
        uuid source_id FK
        text external_id
        uuid customer_id FK
        uuid subscription_id FK
        text status "draft | finalized | paid | void | uncollectible"
        text currency
        bigint subtotal_cents
        bigint tax_cents
        bigint total_cents
        timestamptz period_start
        timestamptz period_end
        timestamptz issued_at
        timestamptz paid_at
        timestamptz voided_at
        timestamptz created_at
    }

    invoice_line_item {
        uuid id PK
        uuid invoice_id FK
        uuid subscription_id FK
        text type "subscription | usage | addon | proration | tax | credit | adjustment"
        text description
        bigint amount_cents
        decimal quantity
        timestamptz period_start
        timestamptz period_end
    }

    payment {
        uuid id PK
        uuid source_id FK
        text external_id
        uuid invoice_id FK
        uuid customer_id FK
        text status "pending | succeeded | failed | refunded"
        bigint amount_cents
        text currency
        text payment_method_type "card | bank_transfer | wallet"
        text failure_reason
        int attempt_count
        timestamptz succeeded_at
        timestamptz failed_at
        timestamptz refunded_at
        timestamptz created_at
    }
```

## Metric Plugin Tables

Each metric plugin creates its own tables, prefixed with `metric_`. These are documented in [Metrics](metrics.md). Summary:

| Plugin | Tables | Purpose |
|--------|--------|---------|
| MRR | `metric_mrr_snapshot`, `metric_mrr_movement` | Current MRR per subscription, MRR change log |
| Churn | `metric_churn_customer_state`, `metric_churn_event` | Customer activity tracking, churn events |
| Retention | `metric_retention_cohort`, `metric_retention_activity` | Cohort membership, monthly activity |
| LTV | `metric_ltv_customer_revenue` | Cumulative revenue per customer |
| Trials | `metric_trial_event` | Trial lifecycle events |

## Event Log

The `event_log` table is a permanent archive of all [internal events](events.md). It serves two purposes:

1. **Replay source** — when Kafka retention expires or when bootstrapping a new deployment
2. **Audit trail** — full history of every billing system change

Events are append-only. The table is never updated or deleted from.

## Indexes

Key indexes beyond primary keys:

```sql
-- Unique billing system IDs
CREATE UNIQUE INDEX ix_customer_source ON customer(source_id, external_id);
CREATE UNIQUE INDEX ix_subscription_source ON subscription(source_id, external_id);
CREATE UNIQUE INDEX ix_invoice_source ON invoice(source_id, external_id);
CREATE UNIQUE INDEX ix_payment_source ON payment(source_id, external_id);

-- Event log queries
CREATE INDEX ix_event_log_type_time ON event_log(type, occurred_at);
CREATE INDEX ix_event_log_customer ON event_log(customer_id, occurred_at);

-- State queries
CREATE INDEX ix_subscription_status ON subscription(status, customer_id);
CREATE INDEX ix_invoice_period ON invoice(period_start, period_end, status);
CREATE INDEX ix_payment_status ON payment(status, created_at);

-- Cohort queries
CREATE INDEX ix_customer_created ON customer(created_at);
```

## Money Handling

All monetary values are stored as **cents (bigint)**. This avoids floating-point precision issues. The metrics package converts to decimal at the query boundary.

- `mrr_cents = 4999` means $49.99/month
- Annual plan at $599/year: `mrr_cents = 59900 / 12 = 4991` (integer division, round down)
- Multi-currency: each record stores its `currency`. Cross-currency aggregation is the consumer's responsibility.
