"""Shared helpers for metric route handlers."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Query
from sqlalchemy import text

from tidemill.metrics.base import QuerySpec

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
    segment: str | None = Query(default=None),
    compare_segments: list[str] = Query(default=[]),
) -> QuerySpec | None:
    """Build a :class:`QuerySpec` from common query-string parameters.

    The ``segment`` and ``compare_segments`` params carry segment IDs only —
    :func:`query_metric` resolves them to :class:`SegmentDef` objects by
    reading the ``segment`` table.  Keeping parse_spec sync avoids coupling
    every route signature to a DB session.
    """
    filters: dict[str, Any] = {}
    for f in filter:
        key, _, value = f.partition("=")
        filters[key] = value
    if not (dimensions or filters or granularity or segment or compare_segments):
        return None
    spec = QuerySpec(dimensions=dimensions, filters=filters, granularity=granularity)
    # Temporarily stash the raw IDs on the spec.  query_metric swaps them
    # for SegmentDefs before the metric ever sees the spec.
    if segment:
        spec.filters = {**spec.filters, "__segment_id__": segment}
    if compare_segments:
        spec.filters = {
            **spec.filters,
            "__compare_segment_ids__": list(compare_segments),
        }
    return spec


async def _resolve_segments(session: AsyncSession, spec: QuerySpec) -> None:
    """Replace ``__segment_id__`` / ``__compare_segment_ids__`` markers on *spec* with real defs.

    Called from :func:`query_metric` before the spec is handed to the
    metric.  Raises :class:`HTTPException` 404 for unknown ids so FastAPI
    surfaces a clean error rather than letting a KeyError bubble up.
    """
    from tidemill.segments.model import parse_definition

    segment_id = spec.filters.pop("__segment_id__", None)
    compare_ids = spec.filters.pop("__compare_segment_ids__", None)

    wanted: list[str] = []
    if segment_id:
        wanted.append(segment_id)
    if compare_ids:
        wanted.extend(compare_ids)
    if not wanted:
        return

    result = await session.execute(
        text("SELECT id, definition FROM segment WHERE id = ANY(:ids)"),
        {"ids": list(set(wanted))},
    )
    defs_by_id = {r["id"]: parse_definition(r["definition"]) for r in result.mappings().all()}

    if segment_id is not None:
        defn = defs_by_id.get(segment_id)
        if defn is None:
            raise HTTPException(status_code=404, detail=f"Unknown segment id: {segment_id}")
        spec.segment = defn
    if compare_ids:
        pairs: list[tuple[str, Any]] = []
        for sid in compare_ids:
            defn = defs_by_id.get(sid)
            if defn is None:
                raise HTTPException(status_code=404, detail=f"Unknown segment id: {sid}")
            pairs.append((sid, defn))
        spec.compare = tuple(pairs)


async def query_metric(metric: str, params: dict[str, Any], spec: QuerySpec | None) -> Any:
    """Create a throwaway :class:`MetricsEngine` and run a single query."""
    from tidemill.api.app import app
    from tidemill.engine import MetricsEngine

    factory = app.state.session_factory
    async with factory() as session:
        if spec is not None:
            await _resolve_segments(session, spec)
        engine = MetricsEngine(db=session)
        result = await engine.query(metric, params, spec)
        return coerce_numerics(result)
