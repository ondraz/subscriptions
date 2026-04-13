"""Shared helpers for metric route handlers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import Query

from tidemill.metrics.base import QuerySpec


def coerce_numerics(val: Any) -> Any:
    """Convert Decimal values to int or float for clean JSON serialization.

    PostgreSQL SUM(bigint) returns numeric, which asyncpg maps to Python
    Decimal.  FastAPI serializes Decimal as a JSON string — this helper
    ensures all monetary values come through as JSON numbers instead.
    """
    if isinstance(val, Decimal):
        as_int = int(val)
        return as_int if val == as_int else float(val)
    if isinstance(val, dict):
        return {k: coerce_numerics(v) for k, v in val.items()}
    if isinstance(val, list):
        return [coerce_numerics(item) for item in val]
    return val


def parse_spec(
    dimensions: list[str] = Query(default=[]),
    filter: list[str] = Query(default=[]),
    granularity: str | None = None,
) -> QuerySpec | None:
    """Build a :class:`QuerySpec` from common query-string parameters."""
    filters: dict[str, Any] = {}
    for f in filter:
        key, _, value = f.partition("=")
        filters[key] = value
    if not dimensions and not filters and not granularity:
        return None
    return QuerySpec(dimensions=dimensions, filters=filters, granularity=granularity)


async def query_metric(metric: str, params: dict[str, Any], spec: QuerySpec | None) -> Any:
    """Create a throwaway :class:`MetricsEngine` and run a single query."""
    from tidemill.api.app import app
    from tidemill.engine import MetricsEngine

    factory = app.state.session_factory
    async with factory() as session:
        engine = MetricsEngine(db=session)
        result = await engine.query(metric, params, spec)
        return coerce_numerics(result)
