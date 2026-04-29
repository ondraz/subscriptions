"""Retention metric endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends

from tidemill.metrics.base import QuerySpec
from tidemill.metrics.route_helpers import parse_spec, query_metric

router = APIRouter(tags=["metrics"])


@router.get("/metrics/retention")
async def get_retention(
    start: date,
    end: date,
    query_type: str = "cohort_matrix",
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric(
        "retention", {"query_type": query_type, "start": start, "end": end}, spec
    )
