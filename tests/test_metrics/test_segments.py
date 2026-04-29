"""Tests for segment compilation → Cube algebra → SQL.

Database-free — each test compiles a SegmentDef against one of the metric
cubes and inspects the generated SQL.  Covers:

- Simple AND / OR groups, nested groups.
- Field-namespace routing (customer.* / subscription.* / attr.* / computed.*).
- Validation: unknown fields, bad ops, type-mismatched values.
- Compare-mode compilation (CROSS JOIN VALUES + compound OR predicate).
- Operator expansion (``contains``, ``is_empty``, ``not in``, ``between``).
- Ratio-metric behaviour: both numerator and denominator see the same
  compare payload (exercised by inspecting the fragments churn/ltv build).
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy.dialects import postgresql

from tidemill.metrics.base import QuerySpec
from tidemill.metrics.churn import ChurnCustomerStateCube, ChurnEventCube, ChurnMetric
from tidemill.metrics.ltv.cubes import LtvInvoiceCube
from tidemill.metrics.mrr import MRRMovementCube, MRRSnapshotCube
from tidemill.metrics.query import FilterExpr
from tidemill.metrics.trials.cubes import TrialCube
from tidemill.segments.model import (
    Compare,
    Segment,
    ValidationError,
    parse_definition,
    serialize_definition,
    validate_definition,
)


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


# ── Parse / serialize ───────────────────────────────────────────────────


class TestParseSerialize:
    def test_round_trip_simple(self):
        raw = {
            "version": 1,
            "root": {
                "op": "and",
                "conditions": [
                    {"field": "customer.country", "op": "=", "value": "US"},
                ],
            },
        }
        defn = parse_definition(raw)
        assert defn.version == 1
        assert defn.root.op == "and"
        assert serialize_definition(defn) == raw

    def test_round_trip_nested(self):
        raw = {
            "version": 1,
            "root": {
                "op": "or",
                "conditions": [
                    {"field": "customer.country", "op": "=", "value": "US"},
                    {
                        "op": "and",
                        "conditions": [
                            {"field": "attr.tier", "op": "=", "value": "enterprise"},
                            {"field": "customer.country", "op": "=", "value": "DE"},
                        ],
                    },
                ],
            },
        }
        defn = parse_definition(raw)
        assert serialize_definition(defn) == raw

    def test_rejects_missing_fields(self):
        with pytest.raises(ValidationError):
            parse_definition({"root": {"op": "and", "conditions": [{"field": "x"}]}})


# ── Validation ──────────────────────────────────────────────────────────


class TestValidation:
    def test_unknown_field(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.nope", "op": "=", "value": "x"}],
                },
            }
        )
        # customer join exists on MRRSnapshot, but there's no check on the
        # specific column — a broad pass.  Validate targets known dims.
        errors = validate_definition(defn, MRRSnapshotCube, attribute_types={})
        assert errors == []  # customer.<col> is not rejected (column check is runtime)

    def test_unknown_attribute(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "attr.unknown", "op": "=", "value": "x"}],
                },
            }
        )
        errors = validate_definition(defn, MRRSnapshotCube, attribute_types={"tier": "string"})
        assert any("unknown attribute" in e for e in errors)

    def test_unknown_operator(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": "foo", "value": "US"}],
                },
            }
        )
        errors = validate_definition(defn, MRRSnapshotCube, attribute_types={})
        assert any("unknown operator" in e for e in errors)

    def test_in_requires_list(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "currency", "op": "in", "value": "USD"}],
                },
            }
        )
        errors = validate_definition(defn, MRRSnapshotCube, attribute_types={})
        assert any("in requires a list" in e for e in errors)

    def test_between_requires_pair(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "currency", "op": "between", "value": ["USD"]}],
                },
            }
        )
        errors = validate_definition(defn, MRRSnapshotCube, attribute_types={})
        assert any("between" in e for e in errors)

    def test_customer_field_requires_customer_join(self):
        """RetentionCohortCube has the customer join — so customer.* passes."""
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": "=", "value": "US"}],
                },
            }
        )
        from tidemill.metrics.retention.cubes import RetentionCohortCube

        errors = validate_definition(defn, RetentionCohortCube, attribute_types={})
        assert errors == []


# ── Simple compilation ──────────────────────────────────────────────────


class TestSegmentToFragment:
    def test_and_group_customer_filter(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [
                        {"field": "customer.country", "op": "=", "value": "US"},
                    ],
                }
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={})
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt)).upper()
        assert "CUSTOMER" in sql
        assert "C.COUNTRY = %(CUSTOMER_COUNTRY_EQ)S" in sql
        assert params["customer_country_eq"] == "US"

    def test_subscription_field(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [
                        {"field": "subscription.status", "op": "=", "value": "active"},
                    ],
                }
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={})
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt))
        assert "sub.status = %(subscription_status_eq)s" in sql
        assert params["subscription_status_eq"] == "active"

    def test_attribute_filter_joins_eav_table(self):
        """attr.tier should LEFT JOIN customer_attribute aliased ca_tier."""
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [
                        {"field": "attr.tier", "op": "=", "value": "enterprise"},
                    ],
                }
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={"tier": "string"})
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt))
        assert "LEFT OUTER JOIN customer_attribute AS ca_tier" in sql
        assert "ca_tier.key = 'tier'" in sql
        assert "ca_tier.value_string = %(attr_tier_eq)s" in sql
        assert params["attr_tier_eq"] == "enterprise"

    def test_attribute_number_type_targets_value_number(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [
                        {"field": "attr.seats", "op": ">=", "value": 10},
                    ],
                }
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={"seats": "number"})
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt))
        assert "ca_seats.value_number" in sql
        assert params["attr_seats_gte"] == 10

    def test_or_group_compiles_to_or(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "or",
                    "conditions": [
                        {"field": "customer.country", "op": "=", "value": "US"},
                        {"field": "customer.country", "op": "=", "value": "DE"},
                    ],
                }
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={})
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt)).upper()
        assert " OR " in sql
        # Two legs → two differently-suffixed params.
        assert "customer_country_eq_or0" in params
        assert "customer_country_eq_or1" in params
        assert params["customer_country_eq_or0"] == "US"
        assert params["customer_country_eq_or1"] == "DE"

    def test_nested_and_inside_or(self):
        defn = parse_definition(
            {
                "root": {
                    "op": "or",
                    "conditions": [
                        {"field": "customer.country", "op": "=", "value": "US"},
                        {
                            "op": "and",
                            "conditions": [
                                {"field": "customer.country", "op": "=", "value": "DE"},
                                {"field": "currency", "op": "=", "value": "EUR"},
                            ],
                        },
                    ],
                }
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={})
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt)).upper()
        assert " OR " in sql
        assert " AND " in sql
        # The nested AND leg's two filters both end with _or1 (the leg index).
        # customer.country goes through _joined_filter (param=customer_country_eq);
        # `currency` is a bare cube dimension so cube.filter names it by dim name only.
        assert "customer_country_eq_or1" in params
        assert "currency_or1" in params

    def test_dedupe_attribute_joins(self):
        """Two filters on the same attr key must share one ca_<k> join."""
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [
                        {"field": "attr.tier", "op": "!=", "value": "free"},
                        {"field": "attr.tier", "op": "!=", "value": "starter"},
                    ],
                }
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={"tier": "string"})
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, _ = q.compile(MRRSnapshotCube)
        sql = _sql(stmt)
        # Exactly one LEFT JOIN to customer_attribute.
        assert sql.count("LEFT OUTER JOIN customer_attribute") == 1


# ── Operator set ────────────────────────────────────────────────────────


class TestOperators:
    def _compile_one(self, op, value):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": op, "value": value}],
                },
            }
        )
        frag = Segment(defn).to_fragment(MRRSnapshotCube, attribute_types={})
        stmt, params = (MRRSnapshotCube.measures.mrr + frag).compile(MRRSnapshotCube)
        return _norm(_sql(stmt)), params

    def test_contains(self):
        sql, params = self._compile_one("contains", "acme")
        assert "ILIKE" in sql.upper()
        assert params["customer_country_ct"] == "%acme%"

    def test_starts_with(self):
        sql, params = self._compile_one("starts_with", "Ac")
        assert "ILIKE" in sql.upper()
        assert params["customer_country_sw"] == "Ac%"

    def test_ends_with(self):
        sql, params = self._compile_one("ends_with", "Inc")
        assert params["customer_country_ew"] == "%Inc"

    def test_not_contains(self):
        sql, _ = self._compile_one("not_contains", "test")
        assert "NOT" in sql.upper()

    def test_is_empty_emits_is_null(self):
        sql, params = self._compile_one("is_empty", None)
        assert "IS NULL" in sql.upper()
        # No bind-param emitted for IS NULL.
        assert "customer_country_null" not in params

    def test_is_not_empty(self):
        sql, _ = self._compile_one("is_not_empty", None)
        assert "IS NOT NULL" in sql.upper()

    def test_not_in(self):
        sql, params = self._compile_one("not in", ["US", "DE"])
        assert "NOT" in sql.upper() and "IN" in sql.upper()
        assert params["customer_country_nin"] == ["US", "DE"]

    def test_escapes_like_wildcards(self):
        r"""%, _, and \\ in values must be escaped so ILIKE is literal."""
        _, params = self._compile_one("contains", "100%")
        # Expect the raw value escaped before being wrapped in '%%'.
        assert params["customer_country_ct"] == "%100\\%%"


# ── Compare mode ────────────────────────────────────────────────────────


class TestCompareMode:
    def test_compare_emits_cross_join_values(self):
        defn_a = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": "=", "value": "US"}],
                },
            }
        )
        defn_b = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": "=", "value": "DE"}],
                },
            }
        )
        frag = Compare.to_fragment(
            MRRSnapshotCube,
            [("seg_a", defn_a), ("seg_b", defn_b)],
            attribute_types={},
        )
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt)).upper()

        # The compile step joins a VALUES subquery aliased seg.
        assert "AS SEG" in sql
        assert "SEGMENT_ID" in sql
        # Compound OR over two legs
        assert " OR " in sql
        # Each branch's filter param is namespaced by its segment_id.
        assert "customer_country_eq_cmp_seg_a" in params
        assert "customer_country_eq_cmp_seg_b" in params

    def test_compare_with_attribute_unions_joins(self):
        defn_a = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "attr.tier", "op": "=", "value": "enterprise"}],
                },
            }
        )
        defn_b = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "attr.tier", "op": "=", "value": "starter"}],
                },
            }
        )
        frag = Compare.to_fragment(
            MRRSnapshotCube,
            [("a", defn_a), ("b", defn_b)],
            attribute_types={"tier": "string"},
        )
        q = MRRSnapshotCube.measures.mrr + frag
        stmt, _ = q.compile(MRRSnapshotCube)
        sql = _sql(stmt)
        # ca_tier is joined exactly once even though both branches reference it.
        assert sql.count("LEFT OUTER JOIN customer_attribute") == 1

    def test_segment_and_compare_compose(self):
        """``segment=`` AND-restricts every row; ``compare_segments=`` slices into per-branch rows.

        The compare layer uses OR-of-ANDs on the compound predicate so the
        universe filter (``segment=``) and the branch slicer compose.
        """
        universe = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "attr.tier", "op": "=", "value": "enterprise"}],
                }
            }
        )
        branch_a = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": "=", "value": "US"}],
                }
            }
        )
        branch_b = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": "=", "value": "DE"}],
                }
            }
        )
        seg_frag = Segment(universe).to_fragment(
            MRRSnapshotCube, attribute_types={"tier": "string"}
        )
        cmp_frag = Compare.to_fragment(
            MRRSnapshotCube,
            [("a", branch_a), ("b", branch_b)],
            attribute_types={"tier": "string"},
        )
        q = MRRSnapshotCube.measures.mrr + seg_frag + cmp_frag
        stmt, params = q.compile(MRRSnapshotCube)
        sql = _norm(_sql(stmt))

        # Universe filter (tier=enterprise) is AND'd at top level —
        # appears as a plain WHERE ca_tier.value_string = ...
        assert "ca_tier.value_string = %(attr_tier_eq)s" in sql
        # Compare legs tag rows with seg.segment_id.
        assert "seg.segment_id" in sql
        # Per-branch customer filters are namespaced.
        assert "customer_country_eq_cmp_a" in params
        assert "customer_country_eq_cmp_b" in params


# ── End-to-end: covers every metric cube ────────────────────────────────


class TestEveryCube:
    @pytest.mark.parametrize(
        "cube",
        [
            MRRSnapshotCube,
            MRRMovementCube,
            ChurnEventCube,
            ChurnCustomerStateCube,
            LtvInvoiceCube,
            TrialCube,
        ],
    )
    def test_customer_filter_routes_through_customer_join(self, cube):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "customer.country", "op": "=", "value": "US"}],
                },
            }
        )
        frag = Segment(defn).to_fragment(cube, attribute_types={})
        # Attach a minimal measure so compile has something to return.
        first_measure = next(iter(cube._measures))
        q = getattr(cube.measures, first_measure) + frag
        stmt, params = q.compile(cube)
        sql = _norm(_sql(stmt))
        assert "c.country" in sql
        assert params["customer_country_eq"] == "US"

    @pytest.mark.parametrize(
        "cube",
        [
            MRRSnapshotCube,
            MRRMovementCube,
            ChurnEventCube,
            ChurnCustomerStateCube,
            LtvInvoiceCube,
            TrialCube,
        ],
    )
    def test_attribute_filter_compiles_on_every_cube(self, cube):
        defn = parse_definition(
            {
                "root": {
                    "op": "and",
                    "conditions": [{"field": "attr.tier", "op": "=", "value": "enterprise"}],
                },
            }
        )
        frag = Segment(defn).to_fragment(cube, attribute_types={"tier": "string"})
        first_measure = next(iter(cube._measures))
        q = getattr(cube.measures, first_measure) + frag
        stmt, params = q.compile(cube)
        sql = _norm(_sql(stmt))
        assert "customer_attribute" in sql
        assert params["attr_tier_eq"] == "enterprise"


# ── Quick sanity on the FilterExpr compound node ────────────────────────


class TestFilterExprKinds:
    def test_simple_kind_default(self):
        f = FilterExpr(column="x", op="=", value=1, param_name="x_eq")
        assert f.kind == "simple"
        assert f.children == ()

    def test_or_kind_holds_children(self):
        a = FilterExpr(column="x", op="=", value=1, param_name="a")
        b = FilterExpr(column="y", op="=", value=2, param_name="b")
        compound = FilterExpr(
            column="", op="=", value=None, param_name="", kind="or", children=(a, b)
        )
        assert compound.kind == "or"
        assert compound.children == (a, b)


# ── Metric-level wiring: spec must reach every sub-query ────────────────


class _CapturingResult:
    """Stand-in for SQLAlchemy Result; metric code only needs .mappings().all()."""

    def mappings(self):
        return self

    def all(self):
        return []


class _CapturingDb:
    """Records every (compiled SQL, bind params) pair the metric executes.

    The Cube algebra is normally compiled via ``compile(cube)`` which returns
    a SQLAlchemy ``Select`` plus a bind-param dict. ``self.db.execute`` is
    called with that pair, so capturing both is enough to assert the segment
    fragment landed in every sub-query.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, stmt, params=None):
        # Skip the attribute_definition lookup — it fires from
        # ``get_attribute_types`` whenever a segment is compiled, and we
        # only want to capture the metric's own cube queries.
        try:
            sql = _norm(_sql(stmt))
        except Exception:  # noqa: BLE001  - text() statements compile via str()
            sql = str(stmt)
        if "attribute_definition" not in sql:
            self.calls.append((sql, dict(params or {})))
        return _CapturingResult()


def _country_spec(country: str = "US") -> QuerySpec:
    """A QuerySpec filtering the universe to ``customer.country = <country>``.

    Skipping ``attr.X`` here avoids needing a real DB to look up the
    attribute type registry; the wiring being tested is the same — both
    paths flow through ``build_spec_fragment``.
    """
    defn = parse_definition(
        {
            "root": {
                "op": "and",
                "conditions": [{"field": "customer.country", "op": "=", "value": country}],
            },
        }
    )
    return QuerySpec(segment=defn)


class TestChurnCustomerDetailWiring:
    """Verify Churn._customer_detail propagates spec into every sub-query."""

    @pytest.mark.asyncio
    async def test_no_spec_emits_no_attr_join(self):
        m = ChurnMetric()
        m.db = _CapturingDb()
        await m._customer_detail(start=None, end=None, spec=None)
        # Every recorded statement should be free of segment-only joins.
        for sql, _ in m.db.calls:
            assert "customer_attribute" not in sql
            # customer.country shouldn't appear unless the cube already
            # selects it; the bare _customer_detail queries don't.
            assert "c.country" not in sql

    @pytest.mark.asyncio
    async def test_spec_filters_every_sub_query(self):
        m = ChurnMetric()
        m.db = _CapturingDb()
        await m._customer_detail(start=None, end=None, spec=_country_spec("US"))
        # 4 sub-queries: active / logo / revenue / starting MRR.
        assert len(m.db.calls) == 4
        # Each must include the customer.country filter (segment was applied).
        for sql, params in m.db.calls:
            assert "c.country" in sql, f"missing segment filter in: {sql}"
            assert params.get("customer_country_eq") == "US"


class TestChurnRevenueEventsWiring:
    """Verify Churn._revenue_events propagates spec into every sub-query."""

    @pytest.mark.asyncio
    async def test_no_spec_emits_no_country_filter(self):
        m = ChurnMetric()
        m.db = _CapturingDb()
        await m._revenue_events(start=None, end=None, spec=None)
        for sql, _ in m.db.calls:
            assert "c.country" not in sql

    @pytest.mark.asyncio
    async def test_spec_filters_every_sub_query(self):
        m = ChurnMetric()
        m.db = _CapturingDb()
        await m._revenue_events(start=None, end=None, spec=_country_spec("DE"))
        # 2 sub-queries: events + starting MRR.
        assert len(m.db.calls) == 2
        for sql, params in m.db.calls:
            assert "c.country" in sql, f"missing segment filter in: {sql}"
            assert params.get("customer_country_eq") == "DE"


class TestLtvCohortWiring:
    """LTV._cohort_ltv already accepts spec — guard against regression."""

    @pytest.mark.asyncio
    async def test_spec_filters_both_sub_queries(self):
        from datetime import date

        from tidemill.metrics.ltv.metric import LtvMetric

        m = LtvMetric()
        m.db = _CapturingDb()
        await m._cohort_ltv(
            start=date(2025, 1, 1),
            end=date(2025, 12, 31),
            spec=_country_spec("GB"),
        )
        # 2 sub-queries: cohort discovery (mm) + revenue (li).
        assert len(m.db.calls) == 2
        for sql, params in m.db.calls:
            assert "c.country" in sql, f"missing segment filter in: {sql}"
            assert params.get("customer_country_eq") == "GB"
