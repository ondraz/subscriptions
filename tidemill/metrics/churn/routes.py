"""Churn metric endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends

from tidemill.metrics.base import QuerySpec
from tidemill.metrics.route_helpers import parse_spec, query_metric

router = APIRouter(tags=["metrics"])


@router.get("/metrics/churn")
async def get_churn(
    start: date,
    end: date,
    type: str = "logo",
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric("churn", {"start": start, "end": end, "type": type}, spec)


@router.get("/metrics/churn/customers")
async def get_churn_customers(
    start: date,
    end: date,
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric("churn", {"start": start, "end": end, "type": "detail"}, spec)


@router.get("/metrics/churn/revenue-events")
async def get_churn_revenue_events(
    start: date,
    end: date,
    spec: QuerySpec | None = Depends(parse_spec),
) -> Any:
    return await query_metric(
        "churn", {"start": start, "end": end, "type": "revenue_events"}, spec
    )
