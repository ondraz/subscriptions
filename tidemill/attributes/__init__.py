"""Customer attribute ingestion & lookup (EAV over ``customer_attribute``)."""

from __future__ import annotations

from tidemill.attributes.ingest import (
    fan_out_customer_metadata,
    infer_type,
    upsert_attribute_definition,
    upsert_customer_attribute,
)
from tidemill.attributes.registry import (
    distinct_values,
    get_attribute_types,
    list_definitions,
)

__all__ = [
    "distinct_values",
    "fan_out_customer_metadata",
    "get_attribute_types",
    "infer_type",
    "list_definitions",
    "upsert_attribute_definition",
    "upsert_customer_attribute",
]
