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


async def list_customer_rows(
    session: AsyncSession,
    *,
    key: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[dict[str, Any]]]:
    """List ingested ``customer_attribute`` rows joined with customer identity.

    Args:
        session: Active async DB session.
        key: Restrict to a single attribute key (matches the table key column).
        search: Optional case-insensitive substring matched against the
            customer's name, email, or external id.
        limit: Page size (clamped to ``[1, 1000]``).
        offset: Row offset for pagination.

    Returns:
        ``(total, rows)``. Each row exposes the resolved customer identity,
        the attribute key, a polymorphic ``value`` string (coalesced from the
        typed value columns), the origin that last wrote it, and
        ``updated_at``.
    """
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    where: list[str] = []
    params: dict[str, Any] = {}
    if key:
        where.append("ca.key = :key")
        params["key"] = key
    if search:
        where.append("(c.name ILIKE :q OR c.email ILIKE :q OR c.external_id ILIKE :q)")
        params["q"] = f"%{search}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    count_result = await session.execute(
        text(
            "SELECT COUNT(*) AS n FROM customer_attribute ca"
            " JOIN customer c ON c.id = ca.customer_id"
            f" {where_sql}"
        ),
        params,
    )
    total = int(count_result.scalar_one() or 0)

    params_paged = {**params, "lim": limit, "off": offset}
    result = await session.execute(
        text(
            "SELECT ca.customer_id, c.external_id AS customer_external_id,"
            "       c.name AS customer_name, c.email AS customer_email,"
            "       ca.key, ca.value_string, ca.value_number,"
            "       ca.value_bool, ca.value_timestamp,"
            "       ca.origin, ca.updated_at"
            " FROM customer_attribute ca"
            " JOIN customer c ON c.id = ca.customer_id"
            f" {where_sql}"
            " ORDER BY ca.updated_at DESC, ca.customer_id, ca.key"
            " LIMIT :lim OFFSET :off"
        ),
        params_paged,
    )

    rows: list[dict[str, Any]] = []
    for r in result.mappings().all():
        if r["value_string"] is not None:
            value: Any = r["value_string"]
        elif r["value_number"] is not None:
            value = float(r["value_number"])
        elif r["value_bool"] is not None:
            value = bool(r["value_bool"])
        elif r["value_timestamp"] is not None:
            value = r["value_timestamp"].isoformat()
        else:
            value = None
        rows.append(
            {
                "customer_id": r["customer_id"],
                "customer_external_id": r["customer_external_id"],
                "customer_name": r["customer_name"],
                "customer_email": r["customer_email"],
                "key": r["key"],
                "value": value,
                "origin": r["origin"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
        )
    return total, rows


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
