# Metrics

> Metric plugin system — each metric manages its own tables, registration, and event processing.
> Last updated: March 2026

## Design

Each metric is a self-contained plugin. A plugin:

1. **Declares its database tables** — the plugin owns its schema, created on registration
2. **Registers itself** — declares a name, the event types it subscribes to, and its query interface
3. **Listens to events** — consumes from Kafka and updates its tables
4. **Exposes queries** — the `MetricsEngine` delegates queries to the appropriate plugin

This means adding a new metric requires zero changes to existing code. Write a plugin, register it, replay events, done.

## Plugin Base Class

```python
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from sqlalchemy import MetaData


class MetricPlugin(ABC):
    """Base class for metric plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin identifier, e.g. 'mrr', 'churn'."""
        ...

    @property
    @abstractmethod
    def event_types(self) -> list[str]:
        """Event types this plugin subscribes to.
        e.g. ['subscription.created', 'subscription.churned']"""
        ...

    @abstractmethod
    def register_tables(self, metadata: MetaData) -> None:
        """Define SQLAlchemy tables owned by this plugin.
        Called once at startup. Alembic picks these up for migrations."""
        ...

    @abstractmethod
    def handle_event(self, event: Event) -> None:
        """Process a single event. Must be idempotent.
        Called by the Kafka consumer for each matching event."""
        ...

    @abstractmethod
    def query(self, params: dict) -> Any:
        """Answer a metric query. Params vary by plugin
        (at, start, end, interval, filters, ...)."""
        ...
```

## Plugin Registry

Plugins register themselves via a decorator:

```python
from subscriptions.metrics import register_metric

@register_metric
class MRRPlugin(MetricPlugin):
    name = "mrr"
    event_types = ["subscription.created", "subscription.activated",
                   "subscription.changed", "subscription.canceled",
                   "subscription.churned", "subscription.reactivated",
                   "subscription.paused", "subscription.resumed"]
    ...
```

At startup, the engine:

1. Discovers all registered plugins
2. Calls `register_tables()` on each — tables are added to the SQLAlchemy metadata
3. Runs Alembic migrations (or `metadata.create_all()` in dev)
4. Starts a Kafka consumer per plugin (consumer group: `subscriptions.metric.{name}`)

## Plugin Lifecycle

```
Startup                     Runtime                        Query
   │                            │                             │
   │  register_tables()         │  Kafka event arrives        │  GET /api/metrics/mrr
   │  create tables if needed   │  ──────────────────►        │  ─────────────────►
   │  seek to last offset       │  handle_event(event)        │  plugin.query(params)
   │                            │  update plugin tables       │  return result
   │                            │  commit offset              │
```

### Replay / Backfill

When a new plugin is added to an existing deployment:

1. Plugin tables are created (empty)
2. Consumer group is new, so Kafka offset starts at the beginning (or reads from `event_log`)
3. All historical events are replayed through `handle_event()`
4. Plugin catches up to head and starts processing live events

To recompute a metric from scratch: reset the consumer group offset to 0 and truncate the plugin's tables.

## Built-in Plugins

### MRR Plugin

**Subscribes to:** `subscription.created`, `subscription.activated`, `subscription.changed`, `subscription.canceled`, `subscription.churned`, `subscription.reactivated`, `subscription.paused`, `subscription.resumed`

**Tables:**

```sql
-- Running MRR snapshot, updated on every subscription event
CREATE TABLE metric_mrr_snapshot (
    id              UUID PRIMARY KEY,
    source_id       UUID NOT NULL,
    customer_id     TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    mrr_cents       BIGINT NOT NULL,        -- current MRR contribution
    snapshot_at     TIMESTAMPTZ NOT NULL,    -- when this state took effect
    UNIQUE(source_id, subscription_id)
);

-- MRR movements (append-only log for breakdown queries)
CREATE TABLE metric_mrr_movement (
    id              UUID PRIMARY KEY,
    event_id        UUID NOT NULL UNIQUE,    -- idempotency: one movement per event
    source_id       UUID NOT NULL,
    customer_id     TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    movement_type   TEXT NOT NULL,           -- new | expansion | contraction | churn | reactivation
    amount_cents    BIGINT NOT NULL,         -- signed: positive for growth, negative for loss
    occurred_at     TIMESTAMPTZ NOT NULL
);
```

**Event handling:**

```python
def handle_event(self, event: Event) -> None:
    match event.type:
        case "subscription.created" | "subscription.activated":
            self._upsert_snapshot(event, event.payload["mrr_cents"])
            self._append_movement(event, "new", event.payload["mrr_cents"])

        case "subscription.changed":
            prev = event.payload["prev_mrr_cents"]
            new = event.payload["new_mrr_cents"]
            self._upsert_snapshot(event, new)
            delta = new - prev
            kind = "expansion" if delta > 0 else "contraction"
            self._append_movement(event, kind, delta)

        case "subscription.churned":
            prev = event.payload["prev_mrr_cents"]
            self._upsert_snapshot(event, 0)
            self._append_movement(event, "churn", -prev)

        case "subscription.reactivated":
            mrr = event.payload["mrr_cents"]
            self._upsert_snapshot(event, mrr)
            self._append_movement(event, "reactivation", mrr)

        case "subscription.paused":
            mrr = event.payload["mrr_cents"]
            self._upsert_snapshot(event, 0)
            self._append_movement(event, "churn", -mrr)  # paused = temporary churn

        case "subscription.resumed":
            mrr = event.payload["mrr_cents"]
            self._upsert_snapshot(event, mrr)
            self._append_movement(event, "reactivation", mrr)
```

**Queries:**

```python
def query(self, params: dict) -> Any:
    match params.get("query_type"):
        case "current":
            # SUM(mrr_cents) from snapshot table
            return self._current_mrr(params.get("at"))

        case "series":
            # Time series from movement table, cumulative sum
            return self._mrr_series(params["start"], params["end"], params["interval"])

        case "breakdown":
            # Net new MRR breakdown from movement table
            return self._mrr_breakdown(params["start"], params["end"])

        case "arr":
            return self._current_mrr(params.get("at")) * 12
```

**SQL for current MRR:**

```sql
SELECT SUM(mrr_cents) / 100.0 AS mrr
FROM metric_mrr_snapshot
WHERE mrr_cents > 0
```

**SQL for net new MRR breakdown over a period:**

```sql
SELECT
    movement_type,
    SUM(amount_cents) / 100.0 AS amount
FROM metric_mrr_movement
WHERE occurred_at BETWEEN :start AND :end
GROUP BY movement_type
```

### Churn Plugin

**Subscribes to:** `subscription.churned`, `subscription.canceled`, `subscription.created`, `subscription.activated`, `subscription.reactivated`

**Tables:**

```sql
-- Tracks which customers are active at any point in time
CREATE TABLE metric_churn_customer_state (
    id                  UUID PRIMARY KEY,
    source_id           UUID NOT NULL,
    customer_id         TEXT NOT NULL,
    active_subscriptions INT NOT NULL DEFAULT 0,
    first_active_at     TIMESTAMPTZ,
    churned_at          TIMESTAMPTZ,
    UNIQUE(source_id, customer_id)
);

-- Churn events for rate calculation
CREATE TABLE metric_churn_event (
    id              UUID PRIMARY KEY,
    event_id        UUID NOT NULL UNIQUE,
    source_id       UUID NOT NULL,
    customer_id     TEXT NOT NULL,
    churn_type      TEXT NOT NULL,   -- logo | revenue
    mrr_cents       BIGINT,          -- revenue lost (for revenue churn)
    occurred_at     TIMESTAMPTZ NOT NULL
);
```

**Queries:**

Logo churn rate:

```sql
-- Customers who churned in period / customers active at period start
SELECT
    (SELECT COUNT(*) FROM metric_churn_event
     WHERE churn_type = 'logo'
       AND occurred_at BETWEEN :start AND :end)::float
    /
    NULLIF((SELECT COUNT(*) FROM metric_churn_customer_state
            WHERE first_active_at < :start
              AND (churned_at IS NULL OR churned_at >= :start)), 0)
    AS logo_churn_rate
```

Revenue churn rate:

```sql
SELECT
    ABS(SUM(CASE WHEN m.movement_type = 'churn' THEN m.amount_cents ELSE 0 END))::float
    /
    NULLIF((SELECT SUM(mrr_cents) FROM metric_mrr_snapshot WHERE snapshot_at < :start), 0)
    AS revenue_churn_rate
FROM metric_mrr_movement m
WHERE m.occurred_at BETWEEN :start AND :end
```

### Retention Plugin

**Subscribes to:** `subscription.created`, `subscription.activated`, `subscription.churned`, `subscription.reactivated`, `customer.created`

**Tables:**

```sql
-- Cohort membership (immutable once set)
CREATE TABLE metric_retention_cohort (
    id              UUID PRIMARY KEY,
    source_id       UUID NOT NULL,
    customer_id     TEXT NOT NULL,
    cohort_month    DATE NOT NULL,          -- month of first subscription
    UNIQUE(source_id, customer_id)
);

-- Monthly activity (one row per customer per active month)
CREATE TABLE metric_retention_activity (
    id              UUID PRIMARY KEY,
    source_id       UUID NOT NULL,
    customer_id     TEXT NOT NULL,
    active_month    DATE NOT NULL,
    UNIQUE(source_id, customer_id, active_month)
);
```

**Query — cohort retention matrix:**

```sql
SELECT
    c.cohort_month,
    a.active_month,
    COUNT(DISTINCT a.customer_id)::float
        / NULLIF(COUNT(DISTINCT c.customer_id), 0) AS retention_rate,
    EXTRACT(MONTH FROM age(a.active_month, c.cohort_month))::int AS months_since
FROM metric_retention_cohort c
LEFT JOIN metric_retention_activity a
    ON c.customer_id = a.customer_id AND c.source_id = a.source_id
WHERE c.cohort_month BETWEEN :start AND :end
GROUP BY c.cohort_month, a.active_month
ORDER BY c.cohort_month, a.active_month
```

**Net Revenue Retention (NRR) and Gross Revenue Retention (GRR):**

These query the MRR plugin's movement table:

```
NRR = (start_mrr + expansion - contraction - churn) / start_mrr
GRR = (start_mrr - contraction - churn) / start_mrr
```

### LTV Plugin

**Subscribes to:** `invoice.paid`, `subscription.churned`, `customer.created`

**Tables:**

```sql
-- Revenue per customer (updated on each paid invoice)
CREATE TABLE metric_ltv_customer_revenue (
    id              UUID PRIMARY KEY,
    source_id       UUID NOT NULL,
    customer_id     TEXT NOT NULL,
    total_cents     BIGINT NOT NULL DEFAULT 0,
    invoice_count   INT NOT NULL DEFAULT 0,
    first_invoice_at TIMESTAMPTZ,
    last_invoice_at TIMESTAMPTZ,
    UNIQUE(source_id, customer_id)
);
```

**Queries:**

Simple LTV: `ARPU / logo_churn_rate`

Cohort LTV: average `total_cents` per customer, grouped by cohort month.

ARPU: `SUM(mrr_cents) / COUNT(DISTINCT active customers)` — queries MRR plugin snapshot.

### Trials Plugin

**Subscribes to:** `subscription.trial_started`, `subscription.trial_converted`, `subscription.trial_expired`

**Tables:**

```sql
CREATE TABLE metric_trial_event (
    id              UUID PRIMARY KEY,
    event_id        UUID NOT NULL UNIQUE,
    source_id       UUID NOT NULL,
    customer_id     TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    event_type      TEXT NOT NULL,       -- started | converted | expired
    occurred_at     TIMESTAMPTZ NOT NULL
);
```

**Query — conversion rate:**

```sql
SELECT
    COUNT(CASE WHEN event_type = 'converted' THEN 1 END)::float /
    NULLIF(COUNT(CASE WHEN event_type = 'started' THEN 1 END), 0)
    AS trial_conversion_rate
FROM metric_trial_event
WHERE occurred_at BETWEEN :start AND :end
```

## MetricsEngine

The engine is the public interface. It discovers plugins and delegates queries:

```python
class MetricsEngine:
    def __init__(self, db, plugins: list[MetricPlugin] | None = None):
        self.db = db
        self.plugins = {p.name: p for p in (plugins or discover_plugins())}

    def mrr(self, at: date | None = None) -> Decimal:
        return self.plugins["mrr"].query({"query_type": "current", "at": at})

    def mrr_series(self, start: date, end: date, interval: str = "month") -> list:
        return self.plugins["mrr"].query({"query_type": "series",
            "start": start, "end": end, "interval": interval})

    def mrr_breakdown(self, start: date, end: date) -> MRRBreakdown:
        return self.plugins["mrr"].query({"query_type": "breakdown",
            "start": start, "end": end})

    def churn_rate(self, start: date, end: date, type: str = "logo") -> Decimal:
        return self.plugins["churn"].query({"start": start, "end": end, "type": type})

    def retention_cohorts(self, start: date, end: date) -> CohortMatrix:
        return self.plugins["retention"].query({"start": start, "end": end})

    def ltv(self, at: date | None = None) -> Decimal:
        return self.plugins["ltv"].query({"at": at})

    def trial_conversion_rate(self, start: date, end: date) -> Decimal:
        return self.plugins["trials"].query({"start": start, "end": end})
```

This is the same interface whether called from FastAPI, Jupyter, or a CLI script.

## Writing a Custom Metric Plugin

Example: a "Quick Ratio" plugin that computes `(new + expansion) / (churn + contraction)`.

```python
from subscriptions.metrics import MetricPlugin, register_metric


@register_metric
class QuickRatioPlugin(MetricPlugin):
    name = "quick_ratio"
    event_types = []  # no events — queries MRR plugin's movement table directly

    def register_tables(self, metadata):
        pass  # no tables needed

    def handle_event(self, event):
        pass  # no events to handle

    def query(self, params):
        # Query MRR movement table directly
        rows = self.db.execute("""
            SELECT movement_type, SUM(amount_cents) AS total
            FROM metric_mrr_movement
            WHERE occurred_at BETWEEN :start AND :end
            GROUP BY movement_type
        """, params)

        growth = sum(r.total for r in rows if r.movement_type in ("new", "expansion", "reactivation"))
        loss = abs(sum(r.total for r in rows if r.movement_type in ("churn", "contraction")))
        return growth / loss if loss > 0 else None
```

This shows how plugins can compose — quick ratio needs no tables or events of its own, it just queries the MRR plugin's data.
