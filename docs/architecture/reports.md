# Reports

> Pre-built charts, styled tables, and analytics for every Tidemill metric.
> Last updated: April 2026

## Overview

`tidemill.reports` provides Plotly charts and pandas Styler tables for subscription analytics. Each metric has its own submodule (`mrr`, `churn`, `retention`, `ltv`, `trials`) following a consistent three-layer pattern:

| Layer | Naming convention | Returns | Purpose |
|-------|-------------------|---------|---------|
| **Data** | `waterfall()`, `timeline()`, … | `DataFrame` or `dict` | Fetch from API, convert cents to dollars |
| **Style** | `style_waterfall()`, … | `pd.io.formats.style.Styler` | Rich table display in Jupyter |
| **Chart** | `plot_waterfall()`, … | `plotly.graph_objects.Figure` | Interactive Plotly visualisation |

## Quick start

```python
from tidemill import reports
from tidemill.reports.client import TidemillClient

reports.setup()                  # activate Tidemill Plotly template
tm = TidemillClient()            # reads TIDEMILL_API env var

# Data → style → chart (each layer is independent)
df = reports.mrr.waterfall(tm, "2025-09-01", "2026-04-30")
reports.mrr.style_waterfall(df)   # styled table
reports.mrr.plot_waterfall(df)    # Plotly figure
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TIDEMILL_API` | `http://localhost:8000` | Tidemill REST API base URL |
| `TIDEMILL_API_KEY` | *(empty)* | Bearer token (omit if auth disabled) |

## Module reference

### `tidemill.reports` (package)

```python
from tidemill import reports
from tidemill.reports import setup, TidemillClient, mrr, churn, retention, ltv, trials
```

`setup()` registers and activates the Tidemill Plotly template (`simple_white+tidemill`). Call it once at the top of a notebook or script.

---

### `tidemill.reports.client`

`TidemillClient` — thin wrapper around the Tidemill REST API. Every metric endpoint has a typed convenience method:

| Method | Returns |
|--------|---------|
| `get(path, **params)` | Generic GET — parsed JSON |
| `mrr(at=None)` | MRR in cents |
| `arr(at=None)` | ARR in cents |
| `mrr_breakdown(start, end)` | List of movement dicts |
| `mrr_waterfall(start, end)` | List of monthly waterfall dicts |
| `churn(start, end, type="logo")` | Churn rate (float or None) |
| `churn_customers(start, end)` | Per-customer churn detail |
| `churn_revenue_events(start, end)` | Per-customer revenue-churn events for active-at-start customers |
| `retention(start, end, **kw)` | Cohort retention data (pass `query_type="nrr"` / `"grr"` / `"cohort_matrix"`) |
| `cohort_matrix(start, end)` | Cohort matrix rows — one per (`cohort_month`, `active_month`) |
| `ltv(start, end)` | Simple LTV in cents |
| `arpu(at=None)` | ARPU in cents |
| `cohort_ltv(start, end)` | Per-cohort LTV breakdown |
| `trial_rate(start, end)` | Trial conversion rate |
| `trial_funnel(start, end)` | Funnel dict |
| `trial_series(start, end, interval)` | Time-series list |
| `sources()` | Connected billing sources |

---

### `tidemill.reports.mrr`

MRR snapshot, breakdown, quick ratio, waterfall, per-customer movement log, and trend.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `snapshot(tm, at=None)` | `TidemillClient`, optional ISO date | `dict` with `mrr`, `arr` (dollars) |
| `breakdown(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `movement_type`, `amount_base`, `amount` |
| `quick_ratio(tm, start, end)` | `TidemillClient`, ISO date range | `dict` with movement components, `gains`, `losses`, `quick_ratio` |
| `waterfall(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with monthly starting/ending MRR and movements (dollars) |
| `movement_log(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with per-customer daily movements (`month`, `date`, `customer_name`, `customer_id`, `movement_type`, `amount`) |
| `trend(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month` and `ending_mrr` (dollars) |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_snapshot(data)` | dict from `snapshot` | Styler — MRR / ARR one-row table |
| `style_waterfall(df)` | DataFrame from `waterfall` | Styler — monthly bridge |
| `style_movement_log(df)` | DataFrame from `movement_log` | Styler with colour-coded movement types and monthly subtotals |
| `style_quick_ratio(data)` | dict from `quick_ratio` | Styler — gains / losses / ratio |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_breakdown(df)` | DataFrame from `breakdown` | Bar chart — MRR movements |
| `plot_waterfall(df)` | DataFrame from `waterfall` | Stacked bar + ending MRR line |
| `plot_trend(df)` | DataFrame from `trend` | Area line — MRR over time |

---

### `tidemill.reports.churn`

Customer churn sets, snapshot, revenue-churn events, monthly timelines, and lost MRR.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `customer_detail(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with per-customer churn detail (C_start / C_churned) |
| `snapshot(tm, start, end, detail=None)` | `TidemillClient`, ISO date range, optional pre-fetched detail | `dict` with churn rates, counts, and MRR totals |
| `revenue_events(tm, start, end, detail=None)` | `TidemillClient`, ISO date range, optional pre-fetched detail | `DataFrame` — one row per C_start customer with their churned MRR |
| `timeline(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `logo_churn`, `revenue_churn` (decimals) |
| `monthly_lost_mrr(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `churn_dollars` |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_snapshot(data)` | dict from `snapshot` | Styler — logo + revenue churn rates with numerator / denominator |
| `style_c_start(detail)` | DataFrame from `customer_detail` | Styler — customers active at period start with MRR |
| `style_c_churned(detail)` | DataFrame from `customer_detail` | Styler — fully churned customers with lost MRR |
| `style_revenue_events(df)` | DataFrame from `revenue_events` | Styler — per-customer revenue-churn table with totals |
| `style_timeline(df)` | DataFrame from `timeline` | Styler — monthly churn rates |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_timeline(df)` | DataFrame from `timeline` | Dual line — logo + revenue churn rates |
| `plot_monthly_lost_mrr(df)` | DataFrame from `monthly_lost_mrr` | Bar chart — churned MRR per month |

---

### `tidemill.reports.retention`

Cohort retention matrix and monthly NRR / GRR tracking.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `cohort(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` indexed by `cohort_month` with `cohort_size` and `M0 … Mn` retention columns (decimals) |
| `nrr_grr(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `nrr`, `grr` (decimals) |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_cohort(df)` | DataFrame from `cohort` | Styler — heatmap-like percentage table |
| `style_nrr_grr(df)` | DataFrame from `nrr_grr` | Styler — monthly NRR / GRR |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_cohort(df)` | DataFrame from `cohort` | Heatmap — cohort retention over months since start |
| `plot_nrr_grr(df)` | DataFrame from `nrr_grr` | Dual line — NRR + GRR with 100% reference |

---

### `tidemill.reports.ltv`

ARPU, simple LTV, implied churn, and cohort LTV breakdowns.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `overview(tm, start, end)` | `TidemillClient`, ISO date range | `dict` with `arpu`, `ltv` (dollars or None), `implied_churn` (decimal or None) |
| `arpu_timeline(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `active_customers`, `mrr_dollars`, `arpu_dollars` |
| `cohort(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `cohort_month`, `customer_count`, `avg_dollars`, `total_dollars` |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_overview(data)` | dict from `overview` | Styler — ARPU, LTV, implied churn |
| `style_arpu_timeline(df)` | DataFrame from `arpu_timeline` | Styler — monthly ARPU, MRR, active customers |
| `style_cohort(df)` | DataFrame from `cohort` | Styler — per-cohort LTV |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_ltv_overview(data)` | dict from `overview` | Indicator — ARPU, churn rate, LTV |
| `plot_arpu_timeline(df)` | DataFrame from `arpu_timeline` | Area line — monthly ARPU |
| `plot_cohort(df)` | DataFrame from `cohort` | Dual bar — avg revenue + customer count per cohort |

---

### `tidemill.reports.trials`

Trial funnel, conversion rates, and monthly outcomes.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `funnel(tm, start, end)` | `TidemillClient`, ISO date range | `dict` with `started`, `converted`, `expired`, `conversion_rate` |
| `timeline(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `period`, `started`, `converted`, `expired`, `conversion_rate` |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_funnel(data)` | dict from `funnel` | Styler |
| `style_timeline(df)` | DataFrame from `timeline` | Styler |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_funnel(data)` | dict from `funnel` | Bar (funnel counts) + pie (conversion rate) |
| `plot_timeline(df)` | DataFrame from `timeline` | Stacked bar (outcomes) + line (conversion rate) |

---

## Styling

### Colour palette

`tidemill.reports._style.COLORS` defines semantic colours used across all charts. The palette is Tailwind-inspired and grouped by what each colour represents:

| Key | Hex | Usage |
|-----|-----|-------|
| `new` / `active` / `converted` / `grr` | `#16A34A` | Positive movements, active subs, converted trials, gross revenue retention |
| `expansion` / `nrr` | `#2563EB` | Expansion MRR, net revenue retention |
| `contraction` | `#EAB308` | Contraction MRR |
| `trialing` | `#F59E0B` | Trialing subscriptions |
| `past_due` | `#EA580C` | Past-due subscriptions |
| `churn` / `canceled` / `expired` / `logo_churn` | `#DC2626` | Lost revenue, churned customers, expired trials |
| `revenue_churn` | `#F59E0B` | Revenue churn (paired with logo churn) |
| `reactivation` | `#8B5CF6` | Reactivation MRR |
| `arpu` | `#8B5CF6` | ARPU lines / indicators |
| `starting_mrr` / `pending` / `grey` | `#78716C` | Starting MRR, pending trials, neutral |

A default multi-series `COLORWAY` is also defined, cycling through amber, blue, green, violet, red, cyan, pink, lime, and stone.

### Plotly template

`setup()` registers a custom Plotly template (`simple_white+tidemill`) that provides:

- **Typography:** Inter font family, stone-grey scheme (titles on `#1C1917`, body on `#44403C`)
- **Layout:** centred titles, 820×520 default size, light stone grid lines, transparent legends
- **Colour scales:** warm orange sequential scale for heatmaps / continuous data
- **Trace defaults:** `cliponaxis=False` on scatter and bar traces so data labels are never clipped at plot boundaries; scatter line width 2.5, zero bar line width

---

## Notebooks

The `docs/notebooks/` directory contains Jupyter notebooks that use the reports library — each code cell is typically a single report call:

| Notebook | Metric | Uses |
|----------|--------|------|
| `01_mrr.ipynb` | MRR | snapshot, breakdown, quick_ratio, waterfall, movement_log, trend |
| `02_churn.ipynb` | Churn | customer_detail (C_start / C_churned), snapshot, revenue_events, timeline, monthly_lost_mrr |
| `03_retention.ipynb` | Retention | cohort matrix, NRR / GRR |
| `04_ltv.ipynb` | LTV | overview, arpu_timeline, cohort |
| `05_trials.ipynb` | Trials | funnel, timeline |
