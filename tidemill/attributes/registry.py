"""Read-side helpers for the attribute registry.

These are thin queries over ``attribute_definition`` and ``customer_attribute``
used by the segment compiler (for type resolution) and the discovery endpoint
(for autocomplete / dropdown UI).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_attribute_types(session: AsyncSession) -> dict[str, str]:
    """Return ``{key: type}`` for every :table:`attribute_definition` row.

    Fetched per-request — the table is small and the lookup only fires when
    a segment is being compiled.  Callers that need it inside a hot path
    should cache the result in request-local state.
    """
    result = await session.execute(text("SELECT key, type FROM attribute_definition"))
    return {r["key"]: r["type"] for r in result.mappings().all()}


async def list_definitions(session: AsyncSession) -> list[dict[str, Any]]:
    """Return every :table:`attribute_definition` row, ordered by key."""
    result = await session.execute(
        text(
            "SELECT key, label, type, source, description, created_at, updated_at"
            " FROM attribute_definition"
            " ORDER BY key"
        )
    )
    return [dict(r) for r in result.mappings().all()]


_VALUE_COLUMN = {
    "string": "value_string",
    "number": "value_number",
    "boolean": "value_bool",
    "timestamp": "value_timestamp",
}


async def distinct_values(
    session: AsyncSession,
    key: str,
    *,
    limit: int = 100,
) -> list[Any]:
    """Return distinct observed values for an attribute (for autocomplete UI).

    Returns an empty list for unknown keys.  The value column is chosen
    from ``attribute_definition.type``; limit is clamped to 1000.
    """
    if limit < 1:
        return []
    limit = min(limit, 1000)

    type_row = await session.execute(
        text("SELECT type FROM attribute_definition WHERE key = :key"),
        {"key": key},
    )
    defn = type_row.mappings().first()
    if defn is None:
        return []
    col = _VALUE_COLUMN[defn["type"]]

    result = await session.execute(
        text(
            f"SELECT DISTINCT {col} AS v FROM customer_attribute"
            " WHERE key = :key AND "
            f" {col} IS NOT NULL ORDER BY v LIMIT :lim"
        ),
        {"key": key, "lim": limit},
    )
    return [r["v"] for r in result.mappings().all()]
