# Reports & Stripe Validation

> Pre-built charts, styled tables, and ground-truth comparison for every Tidemill metric.
> Last updated: April 2026

## Overview

`tidemill.reports` provides Plotly charts and pandas Styler tables for subscription analytics. Each metric has its own submodule (`mrr`, `churn`, `retention`, `ltv`, `trials`) following a consistent three-layer pattern:

| Layer | Naming convention | Returns | Purpose |
|-------|-------------------|---------|---------|
| **Data** | `waterfall()`, `timeline()`, … | `DataFrame` or `dict` | Fetch from API, convert cents to dollars |
| **Style** | `style_waterfall()`, … | `pd.io.formats.style.Styler` | Rich table display in Jupyter |
| **Chart** | `plot_waterfall()`, … | `plotly.graph_objects.Figure` | Interactive Plotly visualisation |

`tidemill.reports.stripecheck` is the data layer — it fetches from the Stripe API, computes ground-truth metrics independently, and compares them with Tidemill's event-driven results.

## Quick start

```python
from tidemill.reports import setup, mrr, churn, retention, ltv, trials
from tidemill.reports.stripecheck import TidemillClient, StripeData

setup()                          # activate Tidemill Plotly template
tm = TidemillClient()            # reads TIDEMILL_API env var
sd = StripeData()                # uses stripe.api_key

# Data → style → chart (each layer is independent)
df = mrr.waterfall(tm, "2025-09-01", "2026-04-30")
mrr.style_waterfall(df)          # styled table
mrr.plot_waterfall(df)           # Plotly figure
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TIDEMILL_API` | `http://localhost:8000` | Tidemill REST API base URL |
| `TIDEMILL_API_KEY` | *(empty)* | Bearer token (omit if auth disabled) |
| `STRIPE_API_KEY` | — | Stripe API key (required for `StripeData`) |

## Module reference

### `tidemill.reports` (package)

```python
from tidemill.reports import setup, mrr, churn, retention, ltv, trials
```

`setup()` registers and activates the Tidemill Plotly template (`simple_white+tidemill`). Call it once at the top of a notebook or script.

---

### `tidemill.reports.mrr`

MRR comparison, breakdown, waterfall, and trend charts.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `stripe_comparison(tm, sd, at=None)` | `TidemillClient`, `StripeData`, optional ISO date | `dict` with `tidemill`, `stripe`, `diff` (dollars), `match` (bool), `arr` |
| `breakdown(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `movement_type`, `amount_base`, `amount` |
| `waterfall(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with monthly starting/ending MRR and movements (dollars) |
| `trend(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month` and `ending_mrr` (dollars) |
| `stripe_status_breakdown(sd)` | `StripeData` | `DataFrame` with `status`, `count`, `mrr` (dollars) |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_stripe_comparison(data)` | dict from `stripe_comparison` | Styler |
| `style_waterfall(df)` | DataFrame from `waterfall` | Styler |
| `style_stripe_status_breakdown(df)` | DataFrame from `stripe_status_breakdown` | Styler |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_breakdown(df)` | DataFrame from `breakdown` | Bar chart — MRR movements |
| `plot_waterfall(df)` | DataFrame from `waterfall` | Stacked bar + ending MRR line |
| `plot_trend(df)` | DataFrame from `trend` | Area line — MRR over time |
| `plot_stripe_status_breakdown(df)` | DataFrame from `stripe_status_breakdown` | Pie (count) + bar (MRR) |

---

### `tidemill.reports.churn`

Churn comparison with Stripe, monthly timelines, and lost MRR.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `stripe_overview(tm, sd, start, end)` | `TidemillClient`, `StripeData`, ISO date range | `dict` with `tidemill`/`stripe` sub-dicts, match booleans, `active_mrr_cents` |
| `timeline(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `logo_churn`, `revenue_churn` (decimals) |
| `monthly_lost_mrr(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `churn_dollars` |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_stripe_overview(data)` | dict from `stripe_overview` | Styler |
| `style_timeline(df)` | DataFrame from `timeline` | Styler |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_stripe_overview(data)` | dict from `stripe_overview` | Pie (logo churn) + bar (revenue impact) |
| `plot_timeline(df)` | DataFrame from `timeline` | Dual line — logo + revenue churn rates |
| `plot_monthly_lost_mrr(df)` | DataFrame from `monthly_lost_mrr` | Bar chart — churned MRR per month |

---

### `tidemill.reports.retention`

Cohort retention heatmaps, average curves, and NRR/GRR tracking.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `stripe_heatmap(sd, start, end)` | `StripeData`, ISO date range | `DataFrame` — retention % matrix (cohort x month-offset). `df.attrs["cohort_sizes"]` has cohort sizes |
| `stripe_curve(sd, start, end)` | `StripeData`, ISO date range | `Series` — average retention % by month offset |
| `nrr_grr(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `nrr`, `grr` (decimals) |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_nrr_grr(df)` | DataFrame from `nrr_grr` | Styler |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
| `plot_stripe_heatmap(df)` | DataFrame from `stripe_heatmap` | Heatmap (RdYlGn, 0–100%) |
| `plot_stripe_curve(avg)` | Series from `stripe_curve` | Area line — average retention curve |
| `plot_nrr_grr(df)` | DataFrame from `nrr_grr` | Dual line — NRR + GRR with 100% reference |

---

### `tidemill.reports.ltv`

ARPU, simple LTV, implied churn, and cohort LTV breakdowns.

#### Data functions

| Function | Inputs | Returns |
|----------|--------|---------|
| `overview(tm, start, end)` | `TidemillClient`, ISO date range | `dict` with `arpu`, `ltv` (dollars or None), `implied_churn` (decimal or None) |
| `arpu_timeline(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `month`, `arpu_dollars` |
| `cohort(tm, start, end)` | `TidemillClient`, ISO date range | `DataFrame` with `cohort_month`, `customer_count`, `avg_dollars`, `total_dollars` |

#### Style functions

| Function | Input | Output |
|----------|-------|--------|
| `style_overview(data)` | dict from `overview` | Styler |
| `style_cohort(df)` | DataFrame from `cohort` | Styler |

#### Chart functions

| Function | Input | Chart type |
|----------|-------|------------|
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

## Stripe validation (`stripecheck`)

The `tidemill.reports.stripecheck` subpackage provides the data layer for comparing Tidemill's event-driven metrics against ground truth computed directly from Stripe API objects.

```python
from tidemill.reports.stripecheck import TidemillClient, StripeData, compare

tm = TidemillClient()
sd = StripeData()

compare.mrr(tm, sd, at="2026-03-01")
# {'tidemill': 100933, 'stripe': 100933, 'diff': 0, 'match': True}
```

### Components

#### `TidemillClient`

Thin wrapper around the Tidemill REST API. Every metric endpoint has a typed convenience method:

| Method | Returns |
|--------|---------|
| `mrr(at=None)` | MRR in cents |
| `arr(at=None)` | ARR in cents |
| `mrr_breakdown(start, end)` | List of movement dicts |
| `mrr_waterfall(start, end)` | List of monthly waterfall dicts |
| `churn(start, end, type="logo")` | Churn rate (float or None) |
| `retention(start, end, **kw)` | Cohort retention data |
| `ltv(start, end)` | Simple LTV in cents |
| `arpu(at=None)` | ARPU in cents |
| `cohort_ltv(start, end)` | Per-cohort LTV breakdown |
| `trial_rate(start, end)` | Trial conversion rate |
| `trial_funnel(start, end)` | Funnel dict |
| `trial_series(start, end, interval)` | Time-series list |
| `sources()` | Connected billing sources |

#### `StripeData`

Lazy-loading container for Stripe subscription data. Hits the Stripe API only on first access and caches the result.

| Property / Method | Description |
|-------------------|-------------|
| `.subscriptions` | DataFrame with `id`, `customer`, `status`, `mrr_cents`, `currency`, `created_at`, `canceled_at`, `trial_start`, `trial_end` |
| `.raw` | Underlying Stripe subscription dicts |
| `.active` | Filtered to `status == "active"` |
| `.canceled` | Filtered to `status == "canceled"` |
| `.summary()` | One-line string with status counts |

In **test/sandbox mode**, `StripeData` iterates over all Test Clocks and fetches subscriptions from each. In live mode, it lists all subscriptions directly.

#### `stripe_metrics`

Ground-truth metric computation from raw Stripe data:

| Function | Description |
|----------|-------------|
| `subscription_mrr(sub)` | MRR contribution of a single subscription (cents). Normalises day/week/month/year intervals |
| `active_mrr(subs)` | Total MRR across active subscriptions (cents) |
| `churn_rates(subs, start, end)` | Logo and revenue churn rates with full breakdown |
| `cohort_retention(subs, start, end)` | Cohort retention matrix (% DataFrame) |

#### `compare`

Side-by-side comparison functions:

| Function | Description |
|----------|-------------|
| `mrr(tm, sd, at=None)` | MRR: Tidemill vs Stripe, with diff and match flag |
| `per_subscription_mrr(sd)` | Per-subscription MRR table for debugging mismatches |
| `churn(tm, sd, start, end)` | Logo + revenue churn comparison |
| `retention(tm, sd, start, end)` | Merged retention DataFrame from both sources |

---

## Styling

### Colour palette

`tidemill.reports._style.COLORS` defines semantic colours used across all charts:

| Key | Hex | Usage |
|-----|-----|-------|
| `new` | `#0D9488` | New MRR, active subscriptions, converted trials, GRR |
| `expansion` | `#2563EB` | Expansion MRR, NRR |
| `contraction` | `#D97706` | Contraction MRR, trialing subscriptions |
| `churn` | `#DC2626` | Churned MRR, canceled subscriptions, expired trials |
| `reactivation` | `#7C3AED` | Reactivation MRR, ARPU |
| `starting_mrr` | `#94A3B8` | Starting MRR bar, grey/neutral |

### Plotly template

`setup()` registers a custom Plotly template (`simple_white+tidemill`) that provides:

- **Typography:** Inter font family, slate colour scheme
- **Layout:** centred titles, 820x520 default size, light grid lines
- **Colour scales:** teal sequential scale for heatmaps
- **Trace defaults:** `cliponaxis=False` on scatter and bar traces so data labels are never clipped at plot boundaries

---

## Notebooks

The `docs/notebooks/` directory contains Jupyter notebooks that use the reports library — each cell is typically a single report call:

| Notebook | Metric |
|----------|--------|
| `01_mrr.ipynb` | MRR comparison, breakdown, waterfall, trend |
| `02_churn.ipynb` | Churn overview, timeline, lost MRR |
| `03_retention.ipynb` | Cohort heatmap, retention curve, NRR/GRR |
| `04_ltv.ipynb` | LTV overview, ARPU timeline, cohort LTV |
| `05_trials.ipynb` | Trial funnel, monthly outcomes |
