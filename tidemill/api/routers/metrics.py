"""Generic metric endpoints (list + query-by-body)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter

from tidemill.metrics.base import QuerySpec
from tidemill.metrics.route_helpers import coerce_numerics, query_metric

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def list_metrics() -> list[str]:
    from tidemill.metrics.registry import discover_metrics

    return sorted(m.name for m in discover_metrics())


@router.get("/metrics/summary")
async def get_summary() -> dict[str, Any]:
    """Return current values for all key metrics in one call."""
    from tidemill.api.app import app
    from tidemill.engine import MetricsEngine

    factory = app.state.session_factory
    async with factory() as session:
        engine = MetricsEngine(db=session)
        result: dict[str, Any] = {}

        today = date.today()
        period_start = today.replace(day=1) - timedelta(days=1)
        period_start = period_start.replace(day=1)  # first of previous month

        queries: dict[str, tuple[str, dict[str, Any]]] = {
            "mrr": ("mrr", {"query_type": "current"}),
            "arr": ("mrr", {"query_type": "arr"}),
            "logo_churn_rate": (
                "churn",
                {"start": period_start, "end": today, "type": "logo"},
            ),
            "revenue_churn_rate": (
                "churn",
                {"start": period_start, "end": today, "type": "revenue"},
            ),
            "nrr": (
                "retention",
                {"query_type": "nrr", "start": period_start, "end": today},
            ),
            "ltv": (
                "ltv",
                {"query_type": "simple", "start": period_start, "end": today},
            ),
            "arpu": ("ltv", {"query_type": "arpu"}),
            "trial_conversion_rate": (
                "trials",
                {"query_type": "conversion_rate", "start": period_start, "end": today},
            ),
        }

        for key, (metric, params) in queries.items():
            try:
                val = await engine.query(metric, params)
                if isinstance(val, dict):
                    result.update(val)
                else:
                    result[key] = val
            except Exception:
                result[key] = None

        # Derive active_customers from MRR snapshot count
        try:
            from tidemill.metrics.mrr.cubes import MRRSnapshotCube

            m = MRRSnapshotCube
            q = m.measures.count + m.where("s.mrr_base_cents", ">", 0)
            stmt, params = q.compile(m)
            r = await session.execute(stmt, params)
            row = r.mappings().first()
            result["active_customers"] = row["subscription_count"] if row else 0
        except Exception:
            result["active_customers"] = None

        # Quick ratio = (new + expansion + reactivation) / (contraction + churn)
        mrr_val = result.get("mrr")
        if mrr_val and mrr_val > 0:
            result["quick_ratio"] = None  # needs waterfall data; leave for now
        else:
            result["quick_ratio"] = None

        return coerce_numerics(result)


@router.post("/metrics/{metric}")
async def post_query_metric(
    metric: str,
    body: dict[str, Any],
) -> Any:
    from tidemill.api.schemas import QuerySpecSchema

    params = body.get("params", {})
    raw_spec = body.get("spec")
    spec = None
    if raw_spec:
        s = QuerySpecSchema(**raw_spec)
        spec = QuerySpec(
            dimensions=s.dimensions,
            filters=s.filters,
            granularity=s.granularity,
        )
    return await query_metric(metric, params, spec)
