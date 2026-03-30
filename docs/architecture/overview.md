# Architecture Overview

> Implementation plan for the open-source subscription analytics engine.
> Last updated: March 2026

## Design Principles

1. **Metrics package first** — the core is a Python library (`subscriptions`), not a web app. FastAPI is a thin facade. You can `import subscriptions` in a Jupyter notebook and query metrics directly.
2. **Event-driven** — billing system webhooks are translated into internal events, published to Kafka, and consumed by metric plugins. Events are the single source of truth.
3. **Metrics are plugins** — each metric (MRR, churn, retention, ...) is a self-contained plugin that declares its database tables, registers itself, and subscribes to the events it needs.
4. **Transparent computation** — every metric has documented, auditable logic. No black boxes.
5. **Connector plugins** — billing systems are data sources. Each connector translates vendor-specific webhooks into internal events. Adding a new billing source means implementing one translator class.
6. **Self-hostable** — PostgreSQL + Kafka + Docker. No external services required.

## System Architecture

```
Billing Systems          Event Bus          Analytics Engine           Consumers

┌─────────┐ webhooks  ┌─────────┐       ┌──────────────────────┐
│  Stripe ├──────────►│         │       │  subscriptions (Py)  │     ┌──────────┐
├─────────┤           │         │       │                      ├────►│  FastAPI │
│   Lago  ├──────────►│  Kafka  ├──────►│  ┌────────────────┐  │     └──────────┘
├─────────┤           │         │       │  │ Metric Plugins │  │     ┌──────────┐
│Kill Bill├──────────►│         │       │  │ MRR│Churn│Ret… │  ├────►│ Jupyter  │
└─────────┘           └─────────┘       │  └────────────────┘  │     └──────────┘
                                        │  ┌────────────────┐  │     ┌──────────┐
     connector translates               │  │   PostgreSQL   │  ├────►│   CLI    │
     webhook → internal event           │  └────────────────┘  │     └──────────┘
     → publishes to Kafka               └──────────────────────┘
```

### Data Flow

1. Billing system sends a webhook (e.g., Stripe `customer.subscription.updated`)
2. **Connector** receives it, translates to an internal event (e.g., `subscription.activated`), publishes to Kafka
3. **Core consumer** updates base tables (customer, subscription, invoice, ...) — the current-state view
4. **Metric plugins** each consume the events they care about and update their own materialized tables
5. **Consumers** (API, Jupyter, CLI) query metric plugins for computed results

## Package Structure

```
subscriptions/
├── __init__.py              # Public API: MetricsEngine, connectors
├── engine.py                # MetricsEngine — queries metric plugins
├── models.py                # SQLAlchemy models + Pydantic schemas
├── database.py              # Database connection and session management
├── events.py                # Internal event schema (dataclasses)
├── bus.py                   # Kafka producer/consumer wrappers
├── state.py                 # Core consumer: events → base tables
├── connectors/
│   ├── __init__.py          # Connector base class + registry
│   ├── stripe.py            # Stripe webhook translator
│   ├── lago.py              # Lago webhook translator
│   └── killbill.py          # Kill Bill webhook translator
├── metrics/
│   ├── __init__.py          # MetricPlugin base class + plugin registry
│   ├── mrr.py               # MRR plugin (MRR, ARR, net new MRR)
│   ├── churn.py             # Churn plugin (logo, revenue, net)
│   ├── retention.py         # Retention plugin (cohorts, NRR, GRR)
│   ├── ltv.py               # LTV plugin (LTV, ARPU)
│   └── trials.py            # Trials plugin (conversion rate)
└── api/
    ├── __init__.py
    └── app.py               # FastAPI facade
```

## Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Data science ecosystem, Jupyter integration |
| Database | PostgreSQL | See [Database](database.md) |
| Message bus | Kafka | Durable, replayable, ordered per partition |
| ORM | SQLAlchemy 2.0 | Async support, mature, works with Alembic |
| Migrations | Alembic | Standard for SQLAlchemy projects |
| API | FastAPI | Async, auto-docs, Pydantic integration |
| Packaging | uv + pyproject.toml | Fast, modern Python tooling |

## Why Kafka

Kafka gives us properties that a simple in-process event bus cannot:

- **Durability** — events survive process restarts. If a metric plugin crashes, it resumes from its last offset.
- **Replay** — add a new metric plugin and replay the full event history to backfill its tables from scratch.
- **Decoupling** — connectors, core state, and metric plugins run independently. A slow metric plugin doesn't block webhook processing.
- **Ordering** — events for a given customer are ordered within a partition (partition by `customer_id`).

For development and single-node deployments, [Redpanda](https://redpanda.com/) is a Kafka-compatible alternative with simpler operations.

## What's Next

- [Events](events.md) — internal event schema and Kafka topics
- [Database](database.md) — core tables, ER diagram, and why PostgreSQL
- [Connectors](connectors.md) — webhook translators for Stripe, Lago, Kill Bill
- [Metrics](metrics.md) — metric plugin system
- [API](api.md) — FastAPI endpoints
