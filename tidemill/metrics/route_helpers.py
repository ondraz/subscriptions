"""Shared helpers for metric route handlers."""

from __future__ import annotations

from typing import Any

from fastapi import Query

from tidemill.metrics.base import QuerySpec


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
        return await engine.query(metric, params, spec)
