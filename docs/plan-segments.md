# Customer Segmentation for Tidemill

## Context

Today Tidemill lets users break down MRR and Churn by a tiny hard-coded list of dimensions (`currency`, `customer_country`, `cancel_reason`) and filter with a naive `key=value` query param. Retention, LTV, and Trials expose no breakdowns at all. There is no notion of customer attributes beyond what Stripe ships on the `customer` row, no way to save reusable filters, and no way to compare multiple customer groups on the same chart.

The goal is a first-class **customer segmentation** layer, inspired by SaaSGrid and ChartMogul:

- **Segments** are named, saved, declarative filters ("Enterprise US", "Churn risk", "Q4-24 cohort").
- Every metric can be **filtered by** a segment and/or **compared across** N segments (the two compose).
- The universe of things a segment can filter on is a union of (a) existing cube dimensions, (b) user-defined attributes ingested from Stripe metadata / CSV / API, and (c) computed attributes derived from existing data (MRR band, tenure, cohort).
- Segment definition must compile through the existing Cube / QueryFragment algebra — no parallel SQL paths, no raw `text()` (project convention per `memory/feedback_all_queries_via_cubes.md`).

Competitor reference:
- **SaaSGrid** — typed attributes (Number/Date/String), ~14 operators, account-vs-contract filter scope, computed attributes (Cohort, ACV), multi-segment compare.
- **ChartMogul** — 6 attribute types, customer-scope filtering, CSV/API/AI enrichment, multi-segment compare.

User decisions (captured 2026-04-24): all four enrichment sources in MVP, workspace-shared segments, all five metrics get segmentation, FE moves to a discovery endpoint.

---

## Architecture at a glance

```
 ┌───────────────┐   ┌────────────────┐   ┌──────────────────────┐
 │ Stripe webhook│   │ CSV upload     │   │ REST /api/customers  │
 │ customer.*    │   │ /api/attributes│   │   /{id}/attributes   │
 └──────┬────────┘   └───────┬────────┘   └───────────┬──────────┘
        │                    │                        │
        └────────────┬───────┴─────────┬──────────────┘
                     ▼                 ▼
              attribute_definition   customer_attribute (EAV)
                     │                 │
                     └────────┬────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────────┐
        │ Cube extensions: dynamic_joins + .attribute()    │
        │ Segment.to_fragment(cube) → QueryFragment        │
        │ Compare.to_fragment(cube, [...]) → QueryFragment │
        └──────────────────────────────────────────────────┘
                              │
                              ▼
                 Existing QueryFragment + compile()
                              │
                              ▼
                     SQLAlchemy Select → Postgres
```

Segments are compiled into `QueryFragment` objects that add filters and joins to the same composed SQL the metric already builds. No parallel path, no string SQL.

---

## Data model

All new tables live in `tidemill/models.py` (shared SQLAlchemy `metadata`), not `models_auth.py` — segments and attributes are workspace-scoped, not user-scoped.

### `attribute_definition` — attribute schema registry

```python
attribute_definition = Table(
    "attribute_definition",
    metadata,
    Column("key", Text, primary_key=True),          # e.g. "tier", "account_manager"
    Column("label", Text, nullable=False),           # human-readable
    Column("type", Text, nullable=False),            # 'string'|'number'|'boolean'|'timestamp'
    Column("source", Text, nullable=False),          # 'stripe'|'csv'|'api'|'computed'
    Column("description", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True)),
)
```

Serves both as typed schema enforcement and as the source for the FE discovery endpoint.

### `customer_attribute` — EAV value rows

```python
customer_attribute = Table(
    "customer_attribute",
    metadata,
    Column("id", Text, primary_key=True),
    Column("source_id", Text, nullable=False),
    Column("customer_id", Text, nullable=False),
    Column("key", Text, ForeignKey("attribute_definition.key"), nullable=False),
    Column("value_string", Text),
    Column("value_number", Numeric),
    Column("value_bool", Boolean),
    Column("value_timestamp", DateTime(timezone=True)),
    Column("origin", Text, nullable=False),          # which source wrote this row
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", "customer_id", "key"),
    Index("ix_customer_attr_key_customer", "key", "source_id", "customer_id"),
)
```

Only one `value_*` column is populated per row, determined by `attribute_definition.type`. The index order `(key, source_id, customer_id)` matches the typical segment query pattern (filter attribute first, then join to customer set).

### `segment` — saved segment definitions (workspace-shared)

```python
segment = Table(
    "segment",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column("description", Text),
    Column("definition", Text, nullable=False),      # JSON SegmentDef
    Column("created_by", Text, ForeignKey("app_user.id")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True)),
)
```

`created_by` captures auditing, but segments are visible to all users (no ownership gate). Mirrors the `saved_chart` JSON-config pattern at `tidemill/models_auth.py:77`.

---

## Ingestion paths

### 1. Stripe passthrough (automatic)

`tidemill/state.py:_handle_customer` currently stores Stripe `customer.metadata` as a JSON string in `customer.metadata_` (line 85). Extend it to additionally fan out into `customer_attribute` rows:

- On first sight of a new key, create an `attribute_definition(key=..., source='stripe', type=inferred)`. Type inference is simple: parse as int/float → `number`; ISO-8601 string → `timestamp`; `"true"/"false"` → `boolean`; else `string`.
- Upsert `customer_attribute` rows only for changed keys (diff against existing rows to avoid write amplification).
- Keep `customer.metadata_` populated for backwards compatibility / raw inspection.

Same treatment for `subscription.metadata` once a `subscription_attribute` sibling table is added (P1, not MVP — Stripe subscription metadata is currently not persisted; skip for now).

### 2. CSV upload

New endpoint `POST /api/attributes/import` in a new `tidemill/api/attributes.py` router:

- Accepts multipart CSV. First column is `customer_id` (or `customer_external_id` / `email`, chosen via form field). Other columns become attribute keys.
- User picks a declared type per new column (FE form), or accepts inferred types. Updates `attribute_definition`.
- Bulk `INSERT ... ON CONFLICT (source_id, customer_id, key) DO UPDATE`.
- Return a summary: rows upserted, unknown customers, type inference decisions.

### 3. REST API

- `POST /api/customers/{customer_id}/attributes` — body `{"tier": "enterprise", "account_manager": "Alice"}`. Upserts rows; creates definitions on first sight.
- `DELETE /api/customers/{customer_id}/attributes/{key}` — remove a row.
- `POST /api/attributes` — create/update an attribute_definition explicitly (for type pinning before upload).

### 4. Computed attributes

Declared on the **cube side**, not the ingestion side. Implemented by adding `Dim` entries whose `column` is an expression rather than a bare column reference. For example, on `MRRSnapshotCube`:

```python
class Dimensions:
    mrr_band = Dim(
        column="CASE WHEN s.mrr_base_cents < 10000 THEN '<$100' ... END",
        label="MRR band",
    )
    tenure_months = Dim(
        column="DATE_PART('month', AGE(CURRENT_DATE, c.created_at))",
        join="customer",
        label="Tenure (months)",
    )
```

The existing `literal_column` path in `tidemill/metrics/query.py:249` already handles raw expressions. `attribute_definition` rows are also written for these with `source='computed'` so the FE picker surfaces them uniformly.

MVP computed set: `mrr_band`, `arr_band`, `tenure_months`, `cohort_month` (harmonize with existing retention cohort assignment).

---

## Cube layer extensions

### `dynamic_joins` on QueryFragment

Extend `QueryFragment` in `tidemill/metrics/query.py:187`:

```python
@dataclass(frozen=True)
class DynamicJoinExpr:
    alias: str              # e.g. "ca_tier"
    table: str              # "customer_attribute"
    on: str                 # "ca_tier.customer_id = c.id AND ca_tier.key = 'tier'"
    depends_on: tuple[str, ...] = ()

@dataclass(frozen=True)
class QueryFragment:
    ...
    dynamic_joins: tuple[DynamicJoinExpr, ...] = ()
```

`__add__` deduplicates by alias. `_apply_joins` (line 351) is extended to merge `model._joins` with the fragment's `dynamic_joins` before topological ordering.

### `Cube.attribute(key, op, value)` factory

New classmethod:

```python
@classmethod
def attribute(cls, key: str, op: str, value: Any) -> QueryFragment:
    defn = attribute_registry.get(key)  # cached lookup in attribute_definition
    alias = f"ca_{_safe(key)}"
    value_col = {
        "string": "value_string",
        "number": "value_number",
        "boolean": "value_bool",
        "timestamp": "value_timestamp",
    }[defn.type]
    join = DynamicJoinExpr(
        alias=alias,
        table="customer_attribute",
        on=f"{alias}.customer_id = c.id AND {alias}.source_id = c.source_id "
           f"AND {alias}.key = '{_escape(key)}'",
        depends_on=("customer",),
    )
    return QueryFragment(
        source=cls.__source__, alias=cls.__alias__,
        dynamic_joins=(join,),
        filters=(FilterExpr(f"{alias}.{value_col}", op, value, f"attr_{_safe(key)}"),),
    )
```

Alias is deterministic: two filters on the same key reuse the same join. Value is bound via the existing `_filter_clause` path — no new operators on the Cube side, just a new way to produce filters against an aliased joined table.

### Expanded operator set

Current ops: `=, !=, >, >=, <, <=, in, between`. Add these to `_filter_clause` (line 392):

- `not in` — negate the existing `in` branch.
- `contains`, `starts_with`, `ends_with`, `not_contains` — `ILIKE` with escaped patterns.
- `is_empty`, `is_not_empty` — `IS NULL` / `IS NOT NULL` (no bind param).

All operators map cleanly to SQLAlchemy Core without raw `text()`.

### `Segment.to_fragment(cube)`

New module `tidemill/segments/model.py`:

```python
@dataclass
class Condition:
    field: str      # "customer.country" | "subscription.status" | "attr.tier" | "computed.mrr_band"
    op: str
    value: Any

@dataclass
class Group:
    op: Literal["and", "or"]
    conditions: list[Union[Condition, "Group"]]

@dataclass
class SegmentDef:
    version: int
    root: Group

class Segment:
    def __init__(self, defn: SegmentDef, name: str | None = None):
        ...

    def to_fragment(self, cube: type[Cube]) -> QueryFragment:
        """Compile to a QueryFragment.

        'and' groups concatenate filters (standard QueryFragment behavior).
        'or' groups are more complex: emit a single FilterExpr with a
        compound ColumnElement by calling a new Cube.or_group() helper
        that builds an OR over child clauses — still bind-param safe, no
        text SQL.
        """
```

The compiler walks the tree:
- `customer.<col>` → `cube.filter(<col>, op, value)` (requires the cube to declare a `customer` join; see audit below)
- `subscription.<col>` → `cube.filter(<col>, op, value)` with the subscription join
- `attr.<key>` → `cube.attribute(key, op, value)`
- `computed.<key>` → `cube.dimension(key)` as a group-by is different; for filters, treat as a regular filter via `cube.filter(key, op, value)` against the expression dim

AND composition is free (monoid `+`). OR requires a new `Cube.or_group([fragments]) -> QueryFragment` helper that wraps child filters with `sqlalchemy.or_()` and returns a fragment carrying one composite `FilterExpr`-like element. Extend `FilterExpr` with a `kind='or'` variant rather than overloading a new type, to keep compilation paths uniform.

### Compare mode: single-query CROSS JOIN

Compare mode (N segments in one result) compiles to one SQL statement, not N parallel queries. The shape:

```sql
SELECT seg.segment_id, <period>, <metric dims>, SUM(s.mrr_base_cents) AS amount
FROM metric_mrr_snapshot s
JOIN customer c ON ...
LEFT JOIN customer_attribute ca_tier   ON ca_tier.customer_id   = c.id AND ca_tier.key   = 'tier'
LEFT JOIN customer_attribute ca_region ON ca_region.customer_id = c.id AND ca_region.key = 'region'
CROSS JOIN (VALUES ('seg_a'), ('seg_b'), ('seg_c')) AS seg(segment_id)
WHERE
    <universe-filter conditions from `segment=` (if any) — AND'd into every row>
AND (
    (seg.segment_id = 'seg_a' AND c.country = :a_country AND ca_tier.value_string = :a_tier)
 OR (seg.segment_id = 'seg_b' AND ca_tier.value_string = :b_tier)
 OR (seg.segment_id = 'seg_c' AND ca_region.value_string = :c_region)
)
GROUP BY seg.segment_id, <period>, <metric dims>
```

Each base row is duplicated N times by the CROSS JOIN; the OR filter keeps a given copy only if that row satisfies the tagged segment's conditions. A customer in both A and B produces two surviving rows (one tagged A, one tagged B), which is the correct overlap semantics. The set of dynamic attribute joins is the **union** across all branches — each `customer_attribute` key joins once, reused across branches that reference it.

Implementation: extend `QueryFragment` with

```python
@dataclass(frozen=True)
class CompareBranch:
    segment_id: str
    filter_fragment: QueryFragment       # carries filters + any extra dynamic_joins
    # dimensions/measures on the branch are ignored — only filters matter

@dataclass(frozen=True)
class QueryFragment:
    ...
    compare: tuple[CompareBranch, ...] = ()
```

Compilation order in `QueryFragment.compile` (extending the existing pipeline at `query.py:214`):

1. Apply static + dynamic joins (union across all compare branches).
2. If `compare` is non-empty: add the `VALUES (...)` CROSS JOIN as `seg`; add `seg.segment_id` as the first GROUP BY dimension.
3. Time grain + regular dimensions + measures (existing behaviour).
4. Combine non-compare filters (AND) with the compare predicate (OR-of-ANDs, each branch tagged with `seg.segment_id = :branch_id`).

`Compare.to_fragment(cube, pairs)` takes `[(segment_id, SegmentDef), ...]` and returns a fragment where `compare` is populated and `dynamic_joins` is the union of each branch's joins. Internal composition reuses `Segment.to_fragment(cube)` to produce each branch's filter fragment — no separate code path for segment→SQL.

Bind-param safety: each branch's filters keep their own param names (already prefixed by field name in `Cube.filter`); segment_id literals go through bindparam too.

**Ratio-metric caveat.** Metrics that compute a ratio (churn rate = churned_count / active_at_start_count) run two internal queries inside `Metric.query()` today. In compare mode, **both** must receive the same `compare` fragment so the numerator and denominator are grouped by segment_id before being divided in Python. `Metric` subclasses already thread `QuerySpec` through their multiple queries — the new `spec.compare` is propagated the same way. Churn's `_logo_rate` / `_revenue_rate` at `tidemill/metrics/churn/metric.py` is the main place to update.

**Performance notes.**
- VALUES with ≤10 entries: negligible planner overhead.
- Join amplification: segments that don't share attributes trigger LEFT JOINs on both attribute keys for every base row, but EAV index `(key, source_id, customer_id)` keeps each join cheap; Postgres hash-joins the ca_* relation once.
- GROUP BY on `(segment_id, period, …)` is identical in cost to grouping by any other extra dimension — Tidemill already does this for `currency + customer_country`.

### Cube audit: ensure every metric joins `customer`

Before shipping, verify each metric's cube has a `customer` join declared. Current state:
- `MRRSnapshotCube`, `MRRMovementCube` — have `customer` join ✓
- `ChurnEventCube`, `ChurnCustomerStateCube` — have `customer` join ✓
- `RetentionCohortCube`, `LtvInvoiceCube` — check; add if missing
- `TrialCube` — check; add if missing

Missing joins must be added as static `JoinDef`s. The dynamic attribute joins declare `depends_on=("customer",)` so `_apply_joins` pulls the customer join in transitively.

### Account vs. contract scope (deferred)

SaaSGrid's account-vs-contract distinction maps onto Tidemill's customer-vs-subscription cubes. MVP supports **account-scope** only (filters always scope on `customer.id`). Contract-scope (filter subscriptions but keep customer) is a P1 follow-up — add a `scope` field to `Condition` and route attribute filters to either the customer join or a subscription-level attribute table when that arrives.

---

## Metric API

### Existing endpoints — additive params

Every metric endpoint (`/api/metrics/{mrr,churn,retention,ltv,trials}` and their sub-paths) accepts two new query params, wired through `route_helpers.parse_spec`:

- `segment: str` — ID of a saved segment to scope the metric to.
- `compare_segments: list[str]` — 1–10 segment IDs to break down by.

`segment` and `compare_segments` compose — they are **not** mutually exclusive. `segment` scopes the universe (AND-restricts every row); `compare_segments` then slices that universe by tagging each surviving row with every branch it matches. Example: `segment=enterprise&compare_segments=us_west,us_east` means "MRR of Enterprise customers, split by region". If a compare branch doesn't intersect the filter segment, its slice is just empty — treated as user input, not an API error.

When `compare_segments` is used, the engine compiles a **single query** that tags each row with matching segments and groups by the synthetic `segment_id` dimension (see §"Compare mode: single-query CROSS JOIN" under Cube extensions). One round-trip, one plan, one scan. Correctness under overlap is preserved because the CROSS JOIN duplicates rows per matching segment rather than using a mutually-exclusive CASE.

`QuerySpec` is extended with two optional fields: `segment: SegmentDef | None` (filter) and `compare: tuple[tuple[str, SegmentDef], ...] | None` (slice, list of `(segment_id, definition)` pairs). They compose via the existing `+`:

```python
fragment = (
    cube.measures.mrr
    + cube.apply_spec(spec)                     # dims/filters/granularity from URL
    + (segment.to_fragment(cube) if segment else QueryFragment())          # universe filter
    + (Compare.to_fragment(cube, compare) if compare else QueryFragment()) # slice
)
```

Because all non-compare filters AND together in the WHERE clause and the compare predicate is itself a single compound OR-of-ANDs ANDed into the same WHERE, the two layers don't interfere.

### New endpoints

Namespaced under `/api/segments`:

- `GET /api/segments` — list all segments (workspace-shared).
- `POST /api/segments` — create. Body: `{name, description?, definition}`.
- `GET /api/segments/{id}` — fetch one.
- `PUT /api/segments/{id}` — update.
- `DELETE /api/segments/{id}` — remove.
- `POST /api/segments/validate` — lint a `definition` without saving: walk the tree, check fields exist, return specific errors. Used by the FE builder for live validation.

Namespaced under `/api/attributes`:

- `GET /api/attributes` — list all `attribute_definition` rows.
- `POST /api/attributes` — create/update a definition.
- `GET /api/attributes/{key}/values?limit=100` — distinct observed values for autocomplete/dropdown UI.
- `POST /api/attributes/import` — CSV upload.
- `POST /api/customers/{id}/attributes` — set on one customer.

### Discovery endpoint

`GET /api/metrics/{name}/fields` returns everything the FE needs to build filter UIs:

```json
{
  "dimensions": [
    {"key": "customer.country", "label": "Country", "type": "string"},
    {"key": "subscription.plan_name", "label": "Plan", "type": "string"},
    {"key": "computed.mrr_band", "label": "MRR band", "type": "string"}
  ],
  "attributes": [
    {"key": "attr.tier", "label": "Tier", "type": "string"},
    {"key": "attr.account_manager", "label": "Account manager", "type": "string"}
  ],
  "time_dimensions": [
    {"key": "snapshot_at", "label": "Snapshot at"}
  ]
}
```

Powered by `Cube.available_dimensions()` + `Cube.available_time_dimensions()` (already exist at `query.py:642`) plus a read of `attribute_definition`.

---

## Frontend changes

### Drop hardcoded dimension lists

Delete `MRR_DIMENSIONS`, `CHURN_DIMENSIONS`, `RETENTION_DIMENSIONS`, `LTV_DIMENSIONS`, `TRIALS_DIMENSIONS` from `frontend/src/lib/constants.ts`. Each report fetches `/api/metrics/{name}/fields` on mount and passes the result to the picker.

### Reuse `DimensionPicker` for group-by

`frontend/src/components/controls/DimensionPicker.tsx` is already generic (takes `available: string[]`). It keeps handling the "break down by" role — with the attribute namespace prefixed (`attr.tier`) as part of the field string. Display label comes from the `/fields` response so we don't have to strip prefixes in the picker.

### New `SegmentBuilder` component

`frontend/src/components/controls/SegmentBuilder.tsx` — a rule builder UI:

- Root: AND / OR selector.
- Each rule row: field dropdown (populated from `/fields`), operator dropdown (operators filtered by the field's type), value input (text / number / date / dropdown of observed values from `GET /api/attributes/{key}/values`).
- Add-rule / add-group buttons at each level; unlimited nesting.
- "Save as segment" → modal → persists via `POST /api/segments`.

### New `SegmentPicker` component

`frontend/src/components/controls/SegmentPicker.tsx` — appears on each report alongside `DimensionPicker`:

- Filter row: single-select dropdown (the `segment=` query param).
- Compare row: multi-select dropdown of up to 10 segments (the `compare_segments=` query param).
- The two rows are independent — users can pick either, both, or neither.
- "Manage segments" link → full-page segment list + builder.

### Wire into reports

Each of `MRRReport.tsx`, `ChurnReport.tsx`, `RetentionReport.tsx`, `LtvReport.tsx`, `TrialsReport.tsx` gets:
- Replaces local `const [dimensions]` with `useFields(metricName)` + `useSegments()`.
- Passes `segment` and/or `compare_segments` through to `useMRR`, `useChurn`, etc. in `frontend/src/hooks/useMetrics.ts`.
- When comparing, the chart pivots on `segment_name` (same code path as pivoting on a dimension value today — `MRRReport.tsx:77` shows the existing pivot logic; it just reads a different key).

---

## Documentation

Update in lockstep with code (CLAUDE.md convention):

- `docs/architecture/segments.md` (new) — the design doc: data model, DSL, cube compilation, scope semantics.
- `docs/architecture/cubes.md` — document `Cube.attribute()`, `dynamic_joins`, the expanded operator set, compare-mode compilation.
- `docs/architecture/api.md` — new endpoints (`/api/segments/*`, `/api/attributes/*`, `/api/metrics/{name}/fields`).
- `docs/architecture/database.md` — three new tables.
- `docs/definitions.md` — segment membership semantics (account-scope; NULL attribute = not-member for non-null operators).
- `CLAUDE.md` — update package structure to include `tidemill/segments/` and `tidemill/attributes/`.

---

## Critical files (paths + role)

**Backend — modify:**
- `tidemill/metrics/query.py` — extend `QueryFragment` with `dynamic_joins` and `compare`; add `Cube.attribute()` and `Cube.or_group()`; expand operator set in `_filter_clause`; extend `compile()` to emit CROSS JOIN + compound predicate when `compare` is set.
- `tidemill/metrics/base.py` — add `segment: SegmentDef | None` and `compare: tuple[tuple[str, SegmentDef], ...] | None` to `QuerySpec`.
- `tidemill/metrics/route_helpers.py` — parse `segment` / `compare_segments` query params; resolve IDs to `SegmentDef`s; attach to `QuerySpec`.
- `tidemill/engine.py` — thread `spec.segment` and `spec.compare` through each metric's `query()`; ratio-metric callsites must reuse the same compare payload for numerator and denominator.
- `tidemill/state.py` — fan out `customer.metadata` into `customer_attribute` rows on customer.created/updated.
- `tidemill/models.py` — declare `attribute_definition`, `customer_attribute`, `segment` tables.
- `tidemill/api/app.py` — mount new routers.
- Each `tidemill/metrics/*/cubes.py` — audit/add `customer` join; add `computed` dimensions (mrr_band, tenure_months, cohort_month).
- Each `tidemill/metrics/*/routes.py` — `/fields` endpoint.
- `tidemill/metrics/churn/metric.py` — ensure `_logo_rate` / `_revenue_rate` propagate the compare payload to both sub-queries.

**Backend — create:**
- `tidemill/segments/__init__.py`
- `tidemill/segments/model.py` — `SegmentDef`, `Condition`, `Group`, `Segment.to_fragment`, `Compare.to_fragment`.
- `tidemill/segments/compiler.py` — walks the tree, emits `QueryFragment`.
- `tidemill/segments/routes.py` — CRUD + validate.
- `tidemill/attributes/__init__.py`
- `tidemill/attributes/routes.py` — list, define, import CSV, set on customer.
- `tidemill/attributes/ingest.py` — Stripe metadata fan-out helper.

**Frontend — modify:**
- `frontend/src/lib/constants.ts` — delete `*_DIMENSIONS` constants.
- `frontend/src/components/reports/{MRR,Churn,Retention,Ltv,Trials}Report.tsx` — wire in `useFields`, `useSegments`, render `SegmentPicker`.
- `frontend/src/hooks/useMetrics.ts` — accept `segment` and `compare_segments` params.

**Frontend — create:**
- `frontend/src/components/controls/SegmentBuilder.tsx`
- `frontend/src/components/controls/SegmentPicker.tsx`
- `frontend/src/pages/SegmentsPage.tsx` — full list / create / edit UI.
- `frontend/src/hooks/useFields.ts`, `useSegments.ts`, `useAttributes.ts`.

**Reuse (don't duplicate):**
- `tidemill/metrics/query.py:Cube` — factories (`dimension`, `filter`, `where`, `time_grain`, `apply_spec`).
- `tidemill/metrics/query.py:Cube.available_dimensions()` — for the `/fields` endpoint.
- `frontend/src/components/controls/DimensionPicker.tsx` — generic, reusable.
- `tidemill/models_auth.py` saved-object pattern — mirrored by `segment` table.
- `tidemill/state.py:_handle_customer` existing upsert path — extend, don't replace.

---

## Verification

**Unit / backend:**
1. `make test` — new tests for `Segment.to_fragment(cube)` and `Compare.to_fragment(cube, [...])` across all five cubes.
2. Test cases: AND-only segments, OR groups, nested groups, attribute + computed + customer-column in one segment, segments with unknown fields (reject with specific error), segments with mismatched types (e.g. `attr.tier > 5` where tier is string — reject), segments with `is_empty` semantics.
3. Test `customer_attribute` fan-out: Stripe webhook creates definitions on first sight; update only modifies changed keys; CSV upload inserts rows; REST API upsert works.
4. Test `compare_segments=A,B`: customer in both appears in both segment rows; result row count matches expected union; exactly one SQL statement is executed.
5. Snapshot the compiled SQL for a representative query (filter segment enterprise + compare by region + `mrr_band >= $500` + tenure > 6mo) to guard against regressions.

**API / integration:**
6. Spin up the full stack (`cd deploy/compose && docker-compose up -d`).
7. Seed with `cd deploy/seed && python stripe_seed.py` — the generated customers have `metadata` on some.
8. `curl /api/attributes` — confirm Stripe metadata keys appear as `source='stripe'` attribute_definitions.
9. `curl -X POST /api/attributes/import` with a CSV adding `tier` and `industry` columns — confirm new definitions and rows.
10. `curl -X POST /api/segments` with an Enterprise-US definition — confirm validation passes; persistence round-trips.
11. `curl /api/metrics/mrr?segment=<id>` — confirm response narrows correctly; compare against unfiltered MRR.
12. `curl "/api/metrics/mrr?compare_segments=<A>,<B>"` — confirm N segment rows; sum matches expectation for non-overlapping segments. With overlap: a customer in both A and B contributes to both totals (check against two separate `segment=<A>` and `segment=<B>` calls).
13. With `LOG_LEVEL=debug`, confirm exactly **one** `SQL:` line is logged per compare-mode request (one query, not N).
14. Churn rate compare: `curl "/api/metrics/churn?compare_segments=<A>,<B>"` — confirm both numerator and denominator are segmented so per-segment rates are correct, not a denominator shared across segments.
15. Combined filter + slice: `curl "/api/metrics/mrr?segment=<enterprise>&compare_segments=<us_west>,<us_east>"` — confirm each slice is restricted to Enterprise customers (sum of slices ≤ plain `segment=<enterprise>` total). Slice that doesn't intersect the filter returns zero, not an error.

**Frontend:**
16. Start dev server (`cd frontend && npm run dev`), open the browser (mcp__chrome-devtools) to the MRR report.
17. Confirm `DimensionPicker` populates from `/api/metrics/mrr/fields` (now includes attribute + computed keys).
18. Open segment builder → create "Enterprise US" (country=US AND attr.tier=enterprise) → save → appears in `SegmentPicker`.
19. Pick "Enterprise US" in the filter row AND pick two region segments in the compare row → confirm MRR chart stacks by region, all bars restricted to Enterprise.
20. Navigate to Retention/LTV/Trials — confirm segment picker shows up and filters the chart.
21. Watch the network tab: no 5xx, response shapes match the hooks.
22. DevTools console: no React key warnings, no unhandled promise rejections.

**Non-regression:**
23. Reload MRRReport without any segment selected — KPI values identical to pre-change baseline (capture before starting).
24. `docker-compose logs api | grep 'SQL:'` — confirm no raw `text()` SQL is emitted for segment-bearing queries (SQL goes through the Cube compile path).

---

## Out of scope (follow-ups)

- **Subscription-scope attributes** (SaaSGrid's "contract-level") — requires `subscription_attribute` table and `scope` routing in the segment compiler.
- **AI enrichment** (ChartMogul's OpenAI scraping of customer websites) — optional future plugin; the REST API endpoint already unblocks external scripts doing this.
- **Materialized compare views** — if a compare with 10 segments over a 2-year daily series shows up as a hot path, cache the compiled query + result per segment-set-hash. Not needed for MVP.
- **Lago / Kill Bill connectors** — their customer metadata models map to the same EAV once P1 connectors ship.
- **Segment change history / versioning** — audit log for segment edits; useful for reproducibility but not MVP.
