"""/api/attributes and customer-attribute REST endpoints.

- ``GET  /attributes``                     — list all definitions
- ``POST /attributes``                     — create/update an attribute_definition
                                             (explicit type pinning; first write wins for type)
- ``GET  /attributes/{key}/values``        — distinct observed values (autocomplete)
- ``POST /attributes/import``              — bulk CSV upload
- ``POST /customers/{id}/attributes``      — set values on one customer
- ``DELETE /customers/{id}/attributes/{k}``— remove a value
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text

from tidemill.api.schemas import (
    AttributeDefinitionCreate,
    AttributeDefinitionUpdate,
    CustomerAttributesSet,
)
from tidemill.attributes.ingest import (
    infer_type,
    upsert_attribute_definition,
    upsert_customer_attribute,
)
from tidemill.attributes.registry import distinct_values, list_definitions

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["attributes"])


async def _get_session() -> Any:
    from tidemill.api.deps import get_session

    async for s in get_session():
        yield s


# ── Attribute definitions ───────────────────────────────────────────────


@router.get("/attributes")
async def list_attributes(
    session: AsyncSession = Depends(_get_session),
) -> list[dict[str, Any]]:
    rows = await list_definitions(session)
    return [
        {
            **{k: v for k, v in r.items() if k not in ("created_at", "updated_at")},
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None,
        }
        for r in rows
    ]


@router.post("/attributes", status_code=201)
async def create_attribute(
    body: AttributeDefinitionCreate,
    session: AsyncSession = Depends(_get_session),
) -> dict[str, Any]:
    if body.type not in ("string", "number", "boolean", "timestamp"):
        raise HTTPException(400, f"Unknown type {body.type!r}")
    row = await upsert_attribute_definition(
        session,
        key=body.key,
        type=body.type,
        label=body.label,
        source="api",
        description=body.description,
    )
    await session.commit()
    return {
        **{k: v for k, v in row.items() if k not in ("created_at", "updated_at")},
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


@router.put("/attributes/{key}")
async def update_attribute(
    key: str,
    body: AttributeDefinitionUpdate,
    session: AsyncSession = Depends(_get_session),
) -> dict[str, str]:
    sets: list[str] = []
    params: dict[str, Any] = {"key": key, "now": datetime.now(UTC)}
    if body.label is not None:
        sets.append("label = :label")
        params["label"] = body.label
    if body.description is not None:
        sets.append("description = :desc")
        params["desc"] = body.description
    if not sets:
        return {"status": "no changes"}
    sets.append("updated_at = :now")
    result = await session.execute(
        text(f"UPDATE attribute_definition SET {', '.join(sets)} WHERE key = :key"),
        params,
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(404, "Attribute not found")
    await session.commit()
    return {"status": "updated"}


@router.get("/attributes/{key}/values")
async def get_attribute_values(
    key: str,
    limit: int = 100,
    session: AsyncSession = Depends(_get_session),
) -> dict[str, Any]:
    values = await distinct_values(session, key, limit=limit)
    # Dates and datetimes serialize to ISO-8601 strings for FE display.
    return {
        "key": key,
        "values": [v.isoformat() if hasattr(v, "isoformat") else v for v in values],
    }


# ── Customer attribute rows ─────────────────────────────────────────────


async def _resolve_customer(
    session: AsyncSession,
    identifier: str,
    *,
    key: str,
) -> dict[str, str] | None:
    """Accept either the internal UUID or an external id/email lookup."""
    if key == "id":
        result = await session.execute(
            text("SELECT id, source_id FROM customer WHERE id = :v"),
            {"v": identifier},
        )
    elif key == "external":
        result = await session.execute(
            text(
                "SELECT id, source_id FROM customer WHERE external_id = :v"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"v": identifier},
        )
    elif key == "email":
        result = await session.execute(
            text(
                "SELECT id, source_id FROM customer WHERE email = :v"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"v": identifier},
        )
    else:
        return None
    row = result.mappings().first()
    if row is None:
        return None
    return {"id": row["id"], "source_id": row["source_id"]}


@router.post("/customers/{customer_id}/attributes")
async def set_customer_attributes(
    customer_id: str,
    body: CustomerAttributesSet,
    session: AsyncSession = Depends(_get_session),
) -> dict[str, Any]:
    """Upsert attributes for one customer.

    Each (key, value) pair is upserted.  If the key doesn't yet have an
    attribute_definition, one is created with an inferred type.
    """
    cust = await _resolve_customer(session, customer_id, key="id")
    if cust is None:
        raise HTTPException(404, f"Customer {customer_id!r} not found")

    existing_types = {
        r["key"]: r["type"]
        for r in (
            await session.execute(
                text(
                    "SELECT ad.key, ad.type FROM attribute_definition ad WHERE ad.key = ANY(:keys)"
                ),
                {"keys": list(body.attributes.keys())},
            )
        )
        .mappings()
        .all()
    }

    upserted = 0
    for key, value in body.attributes.items():
        if key not in existing_types:
            t = infer_type(value)
            await upsert_attribute_definition(session, key=key, type=t, label=key, source="api")
            existing_types[key] = t
        await upsert_customer_attribute(
            session,
            source_id=cust["source_id"],
            customer_id=cust["id"],
            key=key,
            value=value,
            attr_type=existing_types[key],
            origin="api",
        )
        upserted += 1

    await session.commit()
    return {"upserted": upserted}


@router.delete("/customers/{customer_id}/attributes/{key}")
async def delete_customer_attribute(
    customer_id: str,
    key: str,
    session: AsyncSession = Depends(_get_session),
) -> dict[str, str]:
    cust = await _resolve_customer(session, customer_id, key="id")
    if cust is None:
        raise HTTPException(404, f"Customer {customer_id!r} not found")
    result = await session.execute(
        text(
            "DELETE FROM customer_attribute"
            " WHERE source_id = :src AND customer_id = :cid AND key = :key"
        ),
        {"src": cust["source_id"], "cid": cust["id"], "key": key},
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(404, "Attribute row not found")
    await session.commit()
    return {"status": "deleted"}


# ── CSV import ──────────────────────────────────────────────────────────


@router.post("/attributes/import")
async def import_attributes_csv(
    file: UploadFile = File(...),
    id_column: str = Form(default="customer_id"),
    id_kind: str = Form(default="id"),  # "id" | "external" | "email"
    session: AsyncSession = Depends(_get_session),
) -> dict[str, Any]:
    """Bulk-upload attributes from a CSV file.

    The ``id_column`` cell identifies a customer via the scheme in
    ``id_kind``: the internal UUID (default), the connector's external id
    (``external``), or the customer email (``email``).  Every other column
    becomes an attribute key; type is inferred from the first non-empty
    value seen.

    Returns a summary:

    - ``rows_read``        — total CSV rows
    - ``rows_upserted``    — rows that resulted in ≥1 attribute write
    - ``unknown_customers``— ids that didn't match any customer
    - ``keys_created``     — attribute keys for which a new definition was inserted
    """
    if id_kind not in ("id", "external", "email"):
        raise HTTPException(400, f"id_kind must be id|external|email, got {id_kind!r}")

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    fieldnames = reader.fieldnames or []
    if id_column not in fieldnames:
        raise HTTPException(400, f"id_column {id_column!r} not present in CSV header")

    attribute_keys = [k for k in fieldnames if k and k != id_column]
    if not attribute_keys:
        raise HTTPException(400, "CSV has no attribute columns besides the id column")

    # Pre-load existing types; infer for new keys from the first non-empty value.
    types_by_key: dict[str, str] = {
        r["key"]: r["type"]
        for r in (
            await session.execute(
                text("SELECT key, type FROM attribute_definition WHERE key = ANY(:keys)"),
                {"keys": attribute_keys},
            )
        )
        .mappings()
        .all()
    }

    rows_read = 0
    rows_upserted = 0
    unknown: list[str] = []
    keys_created: list[str] = []
    for row in reader:
        rows_read += 1
        identifier = (row.get(id_column) or "").strip()
        if not identifier:
            continue
        cust = await _resolve_customer(session, identifier, key=id_kind)
        if cust is None:
            unknown.append(identifier)
            continue

        wrote_this_row = False
        for key in attribute_keys:
            raw = row.get(key)
            if raw is None or raw == "":
                continue
            if key not in types_by_key:
                inferred = infer_type(raw)
                await upsert_attribute_definition(
                    session, key=key, type=inferred, label=key, source="csv"
                )
                types_by_key[key] = inferred
                keys_created.append(key)
            await upsert_customer_attribute(
                session,
                source_id=cust["source_id"],
                customer_id=cust["id"],
                key=key,
                value=raw,
                attr_type=types_by_key[key],
                origin="csv",
            )
            wrote_this_row = True
        if wrote_this_row:
            rows_upserted += 1

    await session.commit()
    return {
        "rows_read": rows_read,
        "rows_upserted": rows_upserted,
        "unknown_customers": unknown,
        "keys_created": sorted(set(keys_created)),
    }


__all__ = ["router"]
