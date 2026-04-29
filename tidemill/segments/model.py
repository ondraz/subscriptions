"""Segment DSL: declarative filter definitions that compile to QueryFragments.

A :class:`SegmentDef` is a versioned tree of :class:`Group` / :class:`Condition`
nodes.  :class:`Segment` compiles a definition against a given
:class:`tidemill.metrics.query.Cube` into a :class:`QueryFragment` that can be
composed with the metric's own fragment via ``+``.

Field grammar (namespaced to keep cube routing unambiguous):

- ``customer.<col>``      — filter on the customer join alias (``c.<col>``).
- ``subscription.<col>``  — filter on the subscription join alias (``sub.<col>``).
- ``attr.<key>``          — EAV lookup via :meth:`Cube.attribute`.
- ``computed.<name>``     — cube dimension backed by an expression (e.g.
  ``mrr_band``, ``tenure_months``).  Resolves to :meth:`Cube.filter`.
- ``<bare>``              — cube dimension name (backwards-compatible with
  existing filter-param syntax).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tidemill.metrics.query import (
    _OP_SUFFIX,
    CompareBranch,
    FilterExpr,
    QueryFragment,
)

if TYPE_CHECKING:
    from tidemill.metrics.query import Cube


class ValidationError(ValueError):
    """Raised when a SegmentDef references unknown fields or invalid ops."""


# ── AST ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Condition:
    field: str
    op: str
    value: Any = None


@dataclass(frozen=True)
class Group:
    op: str  # "and" | "or"
    conditions: list[Condition | Group] = field(default_factory=list)


@dataclass(frozen=True)
class SegmentDef:
    version: int
    root: Group


# ── Parsing ─────────────────────────────────────────────────────────────


def parse_definition(data: Any) -> SegmentDef:
    """Parse a dict or JSON string into a :class:`SegmentDef`.

    The wire format mirrors the AST:

    .. code-block:: json

        {
          "version": 1,
          "root": {
            "op": "and",
            "conditions": [
              {"field": "customer.country", "op": "=", "value": "US"},
              {"field": "attr.tier", "op": "in", "value": ["enterprise", "plus"]}
            ]
          }
        }
    """
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValidationError(f"SegmentDef must be an object, got {type(data).__name__}")
    version = int(data.get("version", 1))
    root_data = data.get("root") or {"op": "and", "conditions": []}
    return SegmentDef(version=version, root=_parse_group(root_data))


def _parse_group(d: dict[str, Any]) -> Group:
    op = d.get("op", "and")
    if op not in ("and", "or"):
        raise ValidationError(f"Group op must be 'and' or 'or', got {op!r}")
    conditions: list[Condition | Group] = []
    for c in d.get("conditions", []) or []:
        if not isinstance(c, dict):
            raise ValidationError(f"Condition must be an object, got {type(c).__name__}")
        # Distinguish Group from Condition by the presence of "conditions".
        if "conditions" in c:
            conditions.append(_parse_group(c))
        else:
            if "field" not in c or "op" not in c:
                raise ValidationError("Condition must have 'field' and 'op'")
            conditions.append(Condition(field=c["field"], op=c["op"], value=c.get("value")))
    return Group(op=op, conditions=conditions)


def _serialize_group(group: Group) -> dict[str, Any]:
    return {
        "op": group.op,
        "conditions": [
            _serialize_group(c)
            if isinstance(c, Group)
            else {"field": c.field, "op": c.op, "value": c.value}
            for c in group.conditions
        ],
    }


def serialize_definition(defn: SegmentDef) -> dict[str, Any]:
    """Dict representation of a :class:`SegmentDef` (round-trip of parse)."""
    return {"version": defn.version, "root": _serialize_group(defn.root)}


# ── Validation ──────────────────────────────────────────────────────────


_VALID_OPS = set(_OP_SUFFIX) | {"is_empty", "is_not_empty"}
_OPS_WITHOUT_VALUE = {"is_empty", "is_not_empty"}
_OPS_REQUIRING_LIST = {"in", "not in"}
_OPS_REQUIRING_PAIR = {"between"}


def validate_definition(
    defn: SegmentDef,
    cube: type[Cube],
    *,
    attribute_types: dict[str, str],
) -> list[str]:
    """Return a list of error messages.  Empty list means valid.

    Checked:
    - Every ``field`` resolves to a join/dim/attribute the cube knows about.
    - Every ``op`` is known.
    - ``in``/``not in`` values are lists; ``between`` values are 2-element
      sequences; ``is_empty``/``is_not_empty`` have no value.
    - ``attr.*`` keys exist in *attribute_types* (the attribute registry).
    """
    errors: list[str] = []
    _validate_group(defn.root, cube, attribute_types, errors, path="root")
    return errors


def _validate_group(
    group: Group,
    cube: type[Cube],
    attribute_types: dict[str, str],
    errors: list[str],
    *,
    path: str,
) -> None:
    if group.op not in ("and", "or"):
        errors.append(f"{path}: group op must be 'and' or 'or', got {group.op!r}")
    if not group.conditions:
        errors.append(f"{path}: group has no conditions")
    for i, c in enumerate(group.conditions):
        child_path = f"{path}.conditions[{i}]"
        if isinstance(c, Group):
            _validate_group(c, cube, attribute_types, errors, path=child_path)
        else:
            _validate_condition(c, cube, attribute_types, errors, path=child_path)


def _validate_condition(
    cond: Condition,
    cube: type[Cube],
    attribute_types: dict[str, str],
    errors: list[str],
    *,
    path: str,
) -> None:
    if cond.op not in _VALID_OPS:
        errors.append(f"{path}: unknown operator {cond.op!r}")

    if cond.op in _OPS_REQUIRING_LIST and not isinstance(cond.value, (list, tuple)):
        errors.append(f"{path}: {cond.op} requires a list value")
    if cond.op in _OPS_REQUIRING_PAIR and (
        not isinstance(cond.value, (list, tuple)) or len(cond.value) != 2
    ):
        errors.append(f"{path}: 'between' requires a [start, end] pair")
    if cond.op in _OPS_WITHOUT_VALUE and cond.value not in (None, ""):
        errors.append(f"{path}: {cond.op} must not carry a value")

    field = cond.field
    if field.startswith("attr."):
        key = field[len("attr.") :]
        if key not in attribute_types:
            errors.append(f"{path}: unknown attribute {key!r}")
    elif field.startswith("customer."):
        if "customer" not in cube._joins:
            errors.append(f"{path}: {cube.__name__} does not declare a 'customer' join")
    elif field.startswith("subscription."):
        if "subscription" not in cube._joins:
            errors.append(f"{path}: {cube.__name__} does not declare a 'subscription' join")
    elif field.startswith("computed."):
        name = field[len("computed.") :]
        if name not in cube._dimensions:
            errors.append(f"{path}: unknown computed field {name!r}")
    else:
        known = set(cube._dimensions) | set(cube._time_dimensions)
        if field not in known:
            errors.append(f"{path}: unknown field {field!r}")


# ── Compilation ─────────────────────────────────────────────────────────


class Segment:
    """Compiles a :class:`SegmentDef` against a cube.

    The compiled fragment composes with other fragments via ``+``:

    .. code-block:: python

        seg = Segment(defn)
        q = cube.measures.mrr + seg.to_fragment(cube, attribute_types=types)
    """

    def __init__(self, defn: SegmentDef, name: str | None = None) -> None:
        self._defn = defn
        self._name = name

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def definition(self) -> SegmentDef:
        return self._defn

    def to_fragment(
        self,
        cube: type[Cube],
        *,
        attribute_types: dict[str, str],
    ) -> QueryFragment:
        """Compile into a :class:`QueryFragment`.

        Raises :class:`ValidationError` if the definition references fields
        unknown to *cube*.
        """
        return _compile_group(cube, self._defn.root, attribute_types)


class Compare:
    """Compile a list of ``(segment_id, SegmentDef)`` pairs into a compare fragment."""

    @staticmethod
    def to_fragment(
        cube: type[Cube],
        pairs: list[tuple[str, SegmentDef]],
        *,
        attribute_types: dict[str, str],
    ) -> QueryFragment:
        """Build a fragment whose compile emits a CROSS JOIN + compound OR.

        Each pair contributes one :class:`CompareBranch`.  The per-branch
        filter fragments are produced by :class:`Segment.to_fragment` — we
        then suffix each branch's bind-param names with the branch's
        segment_id so the compound OR doesn't collide on shared columns
        (e.g. two branches filtering on ``customer.country``).
        """
        branches: list[CompareBranch] = []
        for seg_id, defn in pairs:
            seg = Segment(defn)
            branch_frag = seg.to_fragment(cube, attribute_types=attribute_types)
            # Namespace each branch's bind-params by segment_id so the OR
            # predicate doesn't overwrite them across branches.
            suffix = f"cmp_{_safe_seg_id(seg_id)}"
            renamed_filters = tuple(_rename_filter(f, suffix) for f in branch_frag.filters)
            namespaced = QueryFragment(
                source=branch_frag.source,
                alias=branch_frag.alias,
                measures=branch_frag.measures,
                dimensions=branch_frag.dimensions,
                filters=renamed_filters,
                joins=branch_frag.joins,
                time_grain=branch_frag.time_grain,
                dynamic_joins=branch_frag.dynamic_joins,
            )
            branches.append(CompareBranch(segment_id=seg_id, filter_fragment=namespaced))
        return QueryFragment(
            source=cube.__source__,
            alias=cube.__alias__,
            compare=tuple(branches),
        )


# ── Internals ───────────────────────────────────────────────────────────


def _compile_group(
    cube: type[Cube],
    group: Group,
    attribute_types: dict[str, str],
) -> QueryFragment:
    if not group.conditions:
        return QueryFragment(source=cube.__source__, alias=cube.__alias__)
    parts = [_compile_node(cube, c, attribute_types) for c in group.conditions]
    if group.op == "and":
        result = parts[0]
        for p in parts[1:]:
            result = result + p
        return result
    if group.op == "or":
        return cube.or_group(parts)
    raise ValidationError(f"Unknown group op {group.op!r}")


def _compile_node(
    cube: type[Cube],
    node: Condition | Group,
    attribute_types: dict[str, str],
) -> QueryFragment:
    if isinstance(node, Group):
        return _compile_group(cube, node, attribute_types)
    return _compile_condition(cube, node, attribute_types)


def _compile_condition(
    cube: type[Cube],
    cond: Condition,
    attribute_types: dict[str, str],
) -> QueryFragment:
    field_name = cond.field
    if field_name.startswith("attr."):
        key = field_name[len("attr.") :]
        attr_type = attribute_types.get(key, "string")
        return cube.attribute(key, cond.op, cond.value, attr_type=attr_type)
    if field_name.startswith("customer."):
        col = field_name[len("customer.") :]
        return _joined_filter(cube, "customer", col, cond.op, cond.value)
    if field_name.startswith("subscription."):
        col = field_name[len("subscription.") :]
        return _joined_filter(cube, "subscription", col, cond.op, cond.value)
    if field_name.startswith("computed."):
        name = field_name[len("computed.") :]
        return cube.filter(name, cond.op, cond.value)
    # Bare: treat as cube dimension or time dimension name.
    return cube.filter(field_name, cond.op, cond.value)


def _joined_filter(
    cube: type[Cube],
    join_name: str,
    col: str,
    op: str,
    value: Any,
) -> QueryFragment:
    jdef = cube._joins.get(join_name)
    if jdef is None:
        raise ValidationError(
            f"{cube.__name__} does not declare a {join_name!r} join — "
            f"cannot filter on {join_name}.{col}"
        )
    alias = jdef.alias
    joins = cube._resolve_join_deps(join_name)
    suffix = _OP_SUFFIX.get(op, "op")
    param = f"{join_name}_{col}_{suffix}"
    return QueryFragment(
        source=cube.__source__,
        alias=cube.__alias__,
        joins=joins,
        filters=(FilterExpr(f"{alias}.{col}", op, value, param),),
    )


def _safe_seg_id(seg_id: str) -> str:
    """Same sanitizer as ``query._safe_key`` — keep them in sync."""
    return "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in seg_id)


def _rename_filter(f: FilterExpr, suffix: str) -> FilterExpr:
    """Suffix bind-param names on every nested filter (AND/OR-safe)."""
    if f.kind in ("and", "or"):
        return FilterExpr(
            column="",
            op="=",
            value=None,
            param_name="",
            kind=f.kind,
            children=tuple(_rename_filter(c, suffix) for c in f.children),
        )
    if not f.param_name:
        return f
    return FilterExpr(
        column=f.column,
        op=f.op,
        value=f.value,
        param_name=f"{f.param_name}_{suffix}",
        kind=f.kind,
        children=f.children,
    )
