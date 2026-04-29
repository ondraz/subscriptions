"""Bridge between :class:`QuerySpec` and the Cube algebra.

The single entry point :func:`build_spec_fragment` takes a cube, a spec, and
a session — looks up attribute types when needed — and returns the composed
:class:`QueryFragment` that layers dimensions, filters, granularity, segment
(universe filter), and compare (per-branch slicing) on top of the cube.

Keeping this in one function means every metric's ``query()`` applies the
spec the same way, which is essential for ratio metrics that run multiple
sub-queries (the numerator and denominator must see the same fragment).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tidemill.attributes.registry import get_attribute_types
from tidemill.metrics.query import QueryFragment
from tidemill.segments.model import Compare, Segment

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tidemill.metrics.base import QuerySpec
    from tidemill.metrics.query import Cube


async def build_spec_fragment(
    cube: type[Cube],
    spec: QuerySpec | None,
    db: AsyncSession,
) -> QueryFragment:
    """Assemble the full QuerySpec as a :class:`QueryFragment`.

    Layering:
    1. ``cube.apply_spec(spec)`` — dimensions / filters / granularity
       declared on the spec via query params.
    2. ``Segment(spec.segment).to_fragment(cube)`` — universe filter
       AND-restricted into every row (if set).
    3. ``Compare.to_fragment(cube, spec.compare)`` — sets the
       ``QueryFragment.compare`` tuple so compile() emits the CROSS JOIN +
       compound OR predicate.

    Attribute types are loaded once per call; callers running many
    sub-queries in a single request can optimize by passing the spec through
    unchanged (the attribute read is cheap — one SELECT of a small table).
    """
    if spec is None:
        return QueryFragment(source=cube.__source__, alias=cube.__alias__)
    frag = cube.apply_spec(spec)
    if spec.segment is None and not spec.compare:
        return frag
    attr_types = await get_attribute_types(db)
    if spec.segment is not None:
        frag = frag + Segment(spec.segment).to_fragment(cube, attribute_types=attr_types)
    if spec.compare:
        frag = frag + Compare.to_fragment(cube, list(spec.compare), attribute_types=attr_types)
    return frag
