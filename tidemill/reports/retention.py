"""Retention reports — data, style, and plotly chart functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from tidemill.reports._style import COLORS

if TYPE_CHECKING:
    from tidemill.reports.stripecheck.stripe_data import StripeData
    from tidemill.reports.stripecheck.tidemill_client import TidemillClient


# ── data ─────────────────────────────────────────────────────────────


def stripe_heatmap(sd: StripeData, start: str, end: str) -> pd.DataFrame:
    """Build cohort retention matrix from Stripe data.

    Args:
        sd: Stripe data source.
        start: ISO date string for calendar range start.
        end: ISO date string for calendar range end.

    Returns:
        Retention percentage DataFrame (cohort x month-offset).
        Cohort sizes available via ``df.attrs["cohort_sizes"]``.
    """
    from tidemill.reports.stripecheck.stripe_metrics import cohort_retention

    return cohort_retention(sd.subscriptions, start, end)


def stripe_curve(sd: StripeData, start: str, end: str) -> pd.Series:
    """Average retention curve across all cohorts.

    Args:
        sd: Stripe data source.
        start: ISO date string for calendar range start.
        end: ISO date string for calendar range end.

    Returns:
        Series of average retention % by month offset.
    """
    from tidemill.reports.stripecheck.stripe_metrics import cohort_retention

    retention_pct = cohort_retention(sd.subscriptions, start, end)
    return retention_pct.mean(axis=0)


def nrr_grr(tm: TidemillClient, start: str, end: str) -> pd.DataFrame:
    """Fetch monthly NRR and GRR from Tidemill.

    Args:
        tm: Tidemill API client.
        start: ISO date string for period start.
        end: ISO date string for period end.

    Returns:
        DataFrame with ``month``, ``nrr``, ``grr`` (as decimals).
    """
    months = pd.date_range(start, end, freq="MS")
    rows: list[dict[str, Any]] = []
    for i in range(len(months) - 1):
        s = months[i].strftime("%Y-%m-%d")
        e = months[i + 1].strftime("%Y-%m-%d")
        nrr_val = tm.retention(s, e, query_type="nrr")
        grr_val = tm.retention(s, e, query_type="grr")
        rows.append(
            {
                "month": months[i].strftime("%Y-%m"),
                "nrr": nrr_val,
                "grr": grr_val,
            }
        )
    return pd.DataFrame(rows)


# ── style ────────────────────────────────────────────────────────────


def style_nrr_grr(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Format NRR/GRR as a styled table with percentage formatting.

    Args:
        df: DataFrame from :func:`nrr_grr`.
    """
    fmt_pct = lambda v: f"{v:.1%}" if v is not None else "N/A"  # noqa: E731
    return df.set_index("month").style.format({"nrr": fmt_pct, "grr": fmt_pct})


def style_stripe_retention(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Format retention matrix as a colour-graded table.

    Args:
        df: Retention matrix from :func:`stripe_heatmap`.
    """
    return df.style.format("{:.0f}%").background_gradient(cmap="RdYlGn", vmin=0, vmax=100)


# ── charts ───────────────────────────────────────────────────────────


def plot_stripe_heatmap(df: pd.DataFrame) -> go.Figure:
    """Cohort retention heatmap.

    Args:
        df: Retention matrix from :func:`stripe_heatmap`.
    """
    fig = px.imshow(
        df,
        text_auto=".0f",
        color_continuous_scale="RdYlGn",
        zmin=0,
        zmax=100,
        labels={"x": "Months since signup", "y": "Cohort month", "color": "Retention %"},
    )
    fig.update_layout(title="Cohort Retention Heatmap (Stripe)", height=350)
    return fig


def plot_stripe_curve(avg: pd.Series) -> go.Figure:
    """Average retention curve.

    Args:
        avg: Series from :func:`stripe_curve` (or ``heatmap_df.mean(axis=0)``).
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=avg.index,
            y=avg.values,
            mode="lines+markers+text",
            fill="tozeroy",
            line={"color": COLORS["nrr"], "width": 2},
            marker={"size": 8},
            text=[f"{v:.0f}%" for v in avg.values],
            textposition="top center",
        )
    )
    fig.update_layout(
        title="Average Retention Curve (Stripe)",
        xaxis_title="Months since signup",
        yaxis_title="Retention %",
        yaxis_ticksuffix="%",
        yaxis_range=[0, 105],
    )
    return fig


def plot_nrr_grr(df: pd.DataFrame) -> go.Figure:
    """Monthly NRR and GRR line chart.

    Args:
        df: DataFrame from :func:`nrr_grr`.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.month,
            y=df.nrr.apply(lambda v: v * 100 if v is not None else None),
            name="NRR",
            mode="lines+markers+text",
            line={"color": COLORS["nrr"], "width": 2.5},
            marker={"size": 8},
            text=[f"{v * 100:.0f}%" if v is not None else "" for v in df.nrr],
            textposition="top center",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.month,
            y=df.grr.apply(lambda v: v * 100 if v is not None else None),
            name="GRR",
            mode="lines+markers+text",
            line={"color": COLORS["grr"], "width": 2.5, "dash": "dash"},
            marker={"size": 8, "symbol": "square"},
            text=[f"{v * 100:.0f}%" if v is not None else "" for v in df.grr],
            textposition="bottom center",
        )
    )
    fig.add_hline(y=100, line_dash="dot", line_color=COLORS["grey"], annotation_text="100%")
    fig.update_layout(
        title="Monthly Revenue Retention",
        yaxis_title="Retention (%)",
        yaxis_ticksuffix="%",
    )
    return fig
