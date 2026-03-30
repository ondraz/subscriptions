# API

> FastAPI facade over the metrics engine.
> Last updated: March 2026

## Design

FastAPI is a thin HTTP layer. Every endpoint delegates to `MetricsEngine`. No business logic lives in the API layer.

```python
from fastapi import FastAPI, Depends
from subscriptions import MetricsEngine
from subscriptions.database import get_db

app = FastAPI(title="Subscriptions API")

def get_engine() -> MetricsEngine:
    return MetricsEngine(get_db())

@app.get("/api/metrics/mrr")
def get_mrr(
    at: date | None = None,
    start: date | None = None,
    end: date | None = None,
    interval: str = "month",
    engine: MetricsEngine = Depends(get_engine),
):
    if start and end:
        return engine.mrr_series(start, end, interval)
    return engine.mrr(at)
```

## Endpoints

### Metrics

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/api/metrics/mrr` | MRR (point or series) |
| `GET` | `/api/metrics/arr` | ARR (point or series) |
| `GET` | `/api/metrics/mrr/breakdown` | Net new MRR breakdown |
| `GET` | `/api/metrics/churn` | Churn rate (logo or revenue) |
| `GET` | `/api/metrics/retention` | Cohort retention matrix |
| `GET` | `/api/metrics/ltv` | LTV (point or series) |
| `GET` | `/api/metrics/arpu` | ARPU (point or series) |
| `GET` | `/api/metrics/trials` | Trial conversion rate |
| `GET` | `/api/metrics/quick-ratio` | Quick ratio |
| `GET` | `/api/metrics/customers` | Customer count (point or series) |
| `GET` | `/api/metrics/summary` | All current metrics in one call |

**Common query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `at` | `date` | Point-in-time query (default: today) |
| `start` | `date` | Series start date |
| `end` | `date` | Series end date |
| `interval` | `string` | `day`, `week`, `month`, `year` |
| `source_id` | `uuid` | Filter to one billing source |
| `plan_id` | `uuid` | Filter by plan |

When `start` and `end` are provided, the endpoint returns a time series. Otherwise it returns a single value.

### Data

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/api/customers` | Paginated customer list |
| `GET` | `/api/customers/{id}` | Customer detail with subscriptions |
| `GET` | `/api/subscriptions` | Paginated subscription list |
| `GET` | `/api/invoices` | Paginated invoice list |

### Connectors

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sources` | List connected billing sources |
| `POST` | `/api/sources` | Add a billing source |
| `POST` | `/api/sources/{id}/backfill` | Trigger historical backfill |
| `POST` | `/api/webhooks/{source_id}` | Webhook receiver (translates and publishes to Kafka) |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness check |
| `GET` | `/readyz` | Readiness check (DB connected) |

## Authentication

Not included in v1. The API is designed to run behind a reverse proxy or VPN. Authentication can be added later via middleware.

## Interactive Documentation

FastAPI auto-generates OpenAPI docs at `/docs` (Swagger UI) and `/redoc`.
