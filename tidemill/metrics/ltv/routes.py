"""LTV metric endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends

from tidemill.metrics.base import QuerySpec
from tidemill.metrics.route_helpers import parse_spec, query_metric

router = APIRouter(tags=["metrics"])


@router.get("/metrics/ltv")
async def get_ltv(
    start: date,
    end: date,
    at: date | None = None,
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric(
        "ltv", {"query_type": "simple", "at": at, "start": start, "end": end}, spec
    )


@router.get("/metrics/ltv/arpu")
async def get_arpu(
    at: date | None = None,
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric("ltv", {"query_type": "arpu", "at": at}, spec)


@router.get("/metrics/ltv/cohort")
async def get_cohort_ltv(
    start: date,
    end: date,
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric("ltv", {"query_type": "cohort", "start": start, "end": end}, spec)
