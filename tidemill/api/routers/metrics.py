"""Generic metric endpoints (list + query-by-body)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from tidemill.metrics.base import QuerySpec
from tidemill.metrics.route_helpers import query_metric

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def list_metrics() -> list[str]:
    from tidemill.metrics.registry import discover_metrics

    return sorted(m.name for m in discover_metrics())


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
