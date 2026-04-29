# Customer Segmentation

Tidemill's segmentation layer lets every metric (MRR, Churn, Retention, LTV,
Trials) be **filtered by** a named customer group ("Enterprise US") or
**compared across** multiple groups on the same chart — all through the
existing `Cube` / `QueryFragment` algebra, with no parallel SQL paths.

## Data model

Three tables in `tidemill/models.py`:

- **`attribute_definition`** — schema registry keyed by attribute name
  (`tier`, `account_manager`). Carries `type` (`string | number | boolean |
  timestamp`), `source` (`stripe | csv | api | computed`), and an optional
  human label.
- **`customer_attribute`** — EAV value rows. One row per `(source_id,
  customer_id, key)` tuple; only the `value_*` column matching the declared
  type is populated. Index `(key, source_id, customer_id)` matches the
  typical segment read pattern (filter attribute first, then narrow to
  customer set).
- **`segment`** — saved segment definitions. JSON-encoded `SegmentDef`
  stored in `definition`, workspace-shared (no per-user filter). Mirrors the
  `saved_chart` pattern in `models_auth.py`.

## Ingestion

Attributes land in `customer_attribute` via four paths:

1. **Stripe passthrough** — `state.py:_handle_customer` fans
   `customer.metadata` into typed rows. First-seen-wins on type inference
   (`"true"/"false"` → boolean, parseable number → number, ISO-8601 →
   timestamp, else string). Existing rows are diffed to avoid write
   amplification on webhook replays.
2. **CSV upload** — `POST /api/attributes/import` with a `customer_id` (or
   `external` / `email`) column and one attribute per remaining column.
3. **REST API** — `POST /api/customers/{id}/attributes` for programmatic
   upserts, `POST /api/attributes` for explicit type pinning.
4. **Computed** — declared on the cube as `Dim` entries whose `column` is a
   SQL expression (`CASE WHEN s.mrr_base_cents < 10000 THEN ...`). MVP set:
   `mrr_band`, `arr_band`, `tenure_months`, `cohort_month`. Surfaced
   through the same `/api/metrics/{name}/fields` endpoint as regular dims.

## Segment DSL

A `SegmentDef` is a versioned tree of `Group` / `Condition` nodes
(`tidemill/segments/model.py`):

```json
{
  "version": 1,
  "root": {
    "op": "and",
    "conditions": [
      {"field": "customer.country", "op": "=", "value": "US"},
      {"field": "attr.tier", "op": "in", "value": ["enterprise", "plus"]},
      {
        "op": "or",
        "conditions": [
          {"field": "computed.mrr_band", "op": "=", "value": ">$1000"},
          {"field": "subscription.collection_method", "op": "=", "value": "send_invoice"}
        ]
      }
    ]
  }
}
```

**Field namespaces:**

| Prefix         | Routes to                                              |
| -------------- | ------------------------------------------------------ |
| `customer.X`   | `c.X` via the cube's `customer` static join            |
| `subscription.X`| `sub.X` via the `subscription` static join            |
| `attr.X`       | `ca_X.value_*` via a dynamic `customer_attribute` LEFT JOIN |
| `computed.X`   | `cube.filter(X, ...)` on a `Dim` with an expression column |
| *bare*         | `cube.filter(X, ...)` — a regular cube dimension       |

**Operators** (all bind-param safe — no raw `text()`):
`= != > >= < <=`, `in`, `not in`, `between`, `contains`, `not_contains`,
`starts_with`, `ends_with`, `is_empty`, `is_not_empty`.

## Compilation

`Segment.to_fragment(cube, attribute_types=…)` walks the tree and produces a
`QueryFragment`:

- **AND groups** concatenate filters via the monoid `+`.
- **OR groups** call `Cube.or_group([frag_a, frag_b, …])` which builds a
  single compound `FilterExpr(kind="or", children=…)` wrapping each leg.
  Each leg's bind-param names are suffixed with `_orN` to avoid collisions
  between legs that filter the same column.
- **`attr.X` filters** add a `DynamicJoinExpr(alias="ca_X", table="customer_attribute",
  on="ca_X.customer_id = c.id AND ca_X.source_id = c.source_id AND ca_X.key = 'X'",
  depends_on=("customer",))`. The join is a LEFT JOIN so `is_empty` / `IS NULL`
  semantics remain correct for customers with no row for that key. The
  alias is deterministic: two filters on the same key share one join.

The fragment composes with the metric's own via `+`. Compilation merges
dynamic joins by alias across self + compare branches, unions the
`depends_on` chain into the static join set, and emits exactly one
LEFT JOIN per attribute key.

### Compare mode

`Compare.to_fragment(cube, [(segment_id, SegmentDef), …])` emits a
`QueryFragment` with `compare=(CompareBranch, …)`. Compile adds:

```sql
... FROM metric_mrr_snapshot s
LEFT JOIN customer_attribute ca_tier ON ca_tier.customer_id = c.id AND ...
CROSS JOIN (VALUES ('seg_a'), ('seg_b')) AS seg(segment_id)
WHERE
  <universe-filter from `segment=` (AND'd into every row, if set)>
  AND (
       (seg.segment_id = 'seg_a' AND <branch A filters>)
    OR (seg.segment_id = 'seg_b' AND <branch B filters>)
  )
GROUP BY seg.segment_id, <period>, <metric dims>
```

A customer in both branches produces two rows (one per tag) — the correct
overlap semantics. The compound predicate is namespaced per branch
(`_cmp_<segment_id>`) so two branches can filter the same column with
different values.

**Ratio-metric caveat.** Metrics that divide two aggregates (churn rate, NRR,
LTV, trial conversion) propagate `spec.compare` to **both** sub-queries so
the numerator and denominator are grouped by `segment_id` before division.
`tidemill/metrics/churn/metric.py` is the reference — `_logo_churn`,
`_revenue_churn`, `_active_at_start_count`, `_mrr_at_start_per_segment` all
accept a spec and return per-segment dicts when compare is set.

## Segment scope

**Account-scope only** for MVP — every segment filter scopes on `customer.id`.
Contract-scope (filtering subscriptions within a matching customer) is a P1
follow-up. When Lago / Kill Bill connectors ship, a `subscription_attribute`
sibling table slots into the same EAV pattern.

## API

Under `/api`:

- **`GET /segments`** — list all (workspace-shared).
- **`POST /segments`** / **`PUT /segments/{id}`** / **`DELETE /segments/{id}`**
- **`POST /segments/validate`** — lint a `SegmentDef` without saving.
- **`GET /attributes`** / **`POST /attributes`** / **`PUT /attributes/{key}`**
- **`GET /attributes/{key}/values`** — distinct observed values for UI autocomplete.
- **`POST /attributes/import`** — multipart CSV upload.
- **`POST /customers/{id}/attributes`** / **`DELETE /customers/{id}/attributes/{k}`**
- **`GET /metrics/{name}/fields`** — discovery: dimensions, time_dimensions,
  attributes (with types + labels). Drives the FE picker.

Every existing metric endpoint accepts two new query params:

- **`segment=<id>`** — universe filter (AND'd into every row).
- **`compare_segments=<id1>&compare_segments=<id2>…`** — compare mode (up to 10).

They compose: `segment` scopes the universe, `compare_segments` slices it
per branch.

## Validation rules

`validate_definition(defn, cube, attribute_types=…)` returns a list of
error messages. Checked:

- `op` is known.
- `in` / `not in` values are lists; `between` values are 2-element pairs;
  `is_empty` / `is_not_empty` must not carry a value.
- `attr.X` keys exist in the passed `attribute_types` map.
- `customer.*` / `subscription.*` fields require the cube to declare the
  matching static join.
- `computed.X` names an existing cube dimension.

## Sub-table coverage

The Churn report's "Customer Detail (active at start)" and "Revenue Churn
Events" sub-tables, plus the LTV "Cohort LTV Detail" sub-table, all honor
the segment universe filter. Compare mode is propagated to the per-customer
tables as a universe-union (one row per customer, not per branch) so the
table layout stays 2-D.

## Non-goals / follow-ups

- Subscription-scope attributes (P1 — needs `subscription_attribute` table).
- AI enrichment (ChartMogul-style web-scraping).
- Segment change history / versioning audit log.
- Materialized compare views for 10-segment × 2-year daily queries.
- Per-segment cohort-matrix retention (retention currently treats compare
  as a universe-union — returns one matrix).
- Per-branch breakdown of the Churn customer-detail and revenue-events
  tables (currently universe-union under compare).
