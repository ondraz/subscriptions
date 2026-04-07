"""Retention metric endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query

from tidemill.metrics.route_helpers import parse_spec, query_metric

router = APIRouter(tags=["metrics"])


@router.get("/metrics/retention")
async def get_retention(
    start: date = Query(...),
    end: date = Query(...),
    query_type: str = "cohort_matrix",
    dimensions: list[str] = Query(default=[]),
    filter: list[str] = Query(default=[]),
    granularity: str | None = None,
) -> Any:
    spec = parse_spec(dimensions, filter, granularity)
    return await query_metric(
        "retention", {"query_type": query_type, "start": start, "end": end}, spec
    )
