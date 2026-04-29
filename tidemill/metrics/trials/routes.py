"""Trials metric endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends

from tidemill.metrics.base import QuerySpec
from tidemill.metrics.route_helpers import parse_spec, query_metric

router = APIRouter(tags=["metrics"])


@router.get("/metrics/trials")
async def get_trial_conversion(
    start: date,
    end: date,
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric(
        "trials", {"query_type": "conversion_rate", "start": start, "end": end}, spec
    )


@router.get("/metrics/trials/series")
async def get_trial_series(
    start: date,
    end: date,
    interval: str = "month",
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric(
        "trials",
        {"query_type": "series", "start": start, "end": end, "interval": interval},
        spec,
    )


@router.get("/metrics/trials/funnel")
async def get_trial_funnel(
    start: date,
    end: date,
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric("trials", {"query_type": "funnel", "start": start, "end": end}, spec)
