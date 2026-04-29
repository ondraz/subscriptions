"""Customer segmentation — saved filter definitions that compile through the Cube algebra."""

from __future__ import annotations

from tidemill.segments.compiler import build_spec_fragment
from tidemill.segments.model import (
    Compare,
    Condition,
    Group,
    Segment,
    SegmentDef,
    ValidationError,
    parse_definition,
    serialize_definition,
    validate_definition,
)

__all__ = [
    "Compare",
    "Condition",
    "Group",
    "Segment",
    "SegmentDef",
    "ValidationError",
    "build_spec_fragment",
    "parse_definition",
    "serialize_definition",
    "validate_definition",
]
