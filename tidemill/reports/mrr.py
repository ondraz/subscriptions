"""MRR reports — data, style, and plotly chart functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import plotly.graph_objects as go

from tidemill.reports._style import COLORS

if TYPE_CHECKING:
    from tidemill.reports.stripecheck.stripe_data import StripeData
    from tidemill.reports.stripecheck.tidemill_client import TidemillClient


# ── data ─────────────────────────────────────────────────────────────


def stripe_comparison(
    tm: TidemillClient,
    sd: StripeData,
    at: str | None = None,
) -> dict[str, Any]:
    """Fetch MRR / ARR from Tidemill and Stripe.

    Args:
        tm: Tidemill API client.
        sd: Stripe data source.
        at: Optional ISO date to query MRR at a specific point.

    Returns:
        Dict with ``tidemill``, ``stripe``, ``diff`` (all dollars),
        ``match`` (bool), ``arr`` (dollars).
    """
    from tidemill.reports.stripecheck.stripe_metrics import active_mrr

    tm_mrr = tm.mrr(at=at)
    st_mrr = active_mrr(sd.subscriptions)
    tm_arr = tm.arr(at=at)
    return {
        "tidemill": tm_mrr / 100,
        "stripe": st_mrr / 100,
        "diff": (tm_mrr - st_mrr) / 100,
        "match": tm_mrr == st_mrr,
        "arr": tm_arr / 100,
    }


def breakdown(tm: TidemillClient, start: str, end: str) -> pd.DataFrame:
    """Fetch MRR movement breakdown.

    Args:
        tm: Tidemill API client.
        start: ISO date string for period start.
        end: ISO date string for period end.

    Returns:
        DataFrame with ``movement_type``, ``amount_base``, ``amount``.
    """
    data = tm.mrr_breakdown(start, end)
    df = pd.DataFrame(data)
    df["amount"] = df["amount_base"] / 100
    return df


def waterfall(tm: TidemillClient, start: str, end: str) -> pd.DataFrame:
    """Fetch monthly MRR waterfall.

    Args:
        tm: Tidemill API client.
        start: ISO date string for period start.
        end: ISO date string for period end.

    Returns:
        DataFrame with one row per month, amounts in dollars.
    """
    raw = tm.mrr_waterfall(start, end)
    df = pd.DataFrame(raw)
    money_cols = [
        "starting_mrr",
        "new",
        "expansion",
        "contraction",
        "churn",
        "reactivation",
        "net_change",
        "ending_mrr",
    ]
    for col in money_cols:
        df[col] = df[col] / 100
    return df


def trend(tm: TidemillClient, start: str, end: str) -> pd.DataFrame:
    """Fetch ending MRR per month.

    Args:
        tm: Tidemill API client.
        start: ISO date string for period start.
        end: ISO date string for period end.

    Returns:
        DataFrame with ``month`` and ``ending_mrr`` (dollars).
    """
    raw = tm.mrr_waterfall(start, end)
    df = pd.DataFrame(raw)
    df["ending_mrr"] = df["ending_mrr"] / 100
    return df


def stripe_status_breakdown(sd: StripeData) -> pd.DataFrame:
    """Subscription count and MRR grouped by Stripe status.

    Args:
        sd: Stripe data source.

    Returns:
        Summary DataFrame with ``status``, ``count``, ``mrr`` (dollars).
    """
    df = sd.subscriptions
    summary = (
        df.groupby("status")
        .agg(count=("id", "count"), mrr_cents=("mrr_cents", "sum"))
        .reset_index()
    )
    summary["mrr"] = summary.mrr_cents / 100
    return summary


# ── style ────────────────────────────────────────────────────────────


def style_stripe_comparison(data: dict[str, Any]) -> pd.io.formats.style.Styler:
    """Format comparison dict as a styled table.

    Args:
        data: Dict from :func:`stripe_comparison`.
    """
    df = pd.DataFrame(
        [
            {
                "MRR (Tidemill)": data["tidemill"],
                "MRR (Stripe)": data["stripe"],
                "Difference": data["diff"],
                "Match": data["match"],
                "ARR": data["arr"],
            }
        ]
    )
    return df.style.format(
        {
            "MRR (Tidemill)": "${:,.2f}",
            "MRR (Stripe)": "${:,.2f}",
            "Difference": "${:,.2f}",
            "ARR": "${:,.2f}",
        }
    ).hide(axis="index")


def style_waterfall(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Format waterfall DataFrame as a styled table.

    Args:
        df: DataFrame from :func:`waterfall`.
    """
    display_cols = [
        "starting_mrr",
        "new",
        "expansion",
        "reactivation",
        "contraction",
        "churn",
        "net_change",
        "ending_mrr",
    ]
    styled = df.set_index("month")[display_cols]
    return styled.style.format("${:,.2f}")


def style_stripe_status_breakdown(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Format status breakdown as a styled table.

    Args:
        df: DataFrame from :func:`stripe_status_breakdown`.
    """
    return df[["status", "count", "mrr"]].style.format({"mrr": "${:,.2f}"}).hide(axis="index")


# ── charts ───────────────────────────────────────────────────────────


def plot_breakdown(df: pd.DataFrame) -> go.Figure:
    """Bar chart of MRR movements.

    Args:
        df: DataFrame from :func:`breakdown`.
    """
    fig = go.Figure(
        go.Bar(
            x=df.movement_type,
            y=df.amount,
            marker_color=[COLORS.get(t, COLORS["grey"]) for t in df.movement_type],
            text=[f"${v:,.0f}" for v in df.amount],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="MRR Movements",
        yaxis_title="Amount ($)",
        yaxis_tickprefix="$",
        yaxis_tickformat=",",
    )
    return fig


def plot_waterfall(df: pd.DataFrame) -> go.Figure:
    """Monthly MRR waterfall stacked bar + ending MRR line.

    Args:
        df: DataFrame from :func:`waterfall`.
    """
    dm = df.set_index("month")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Starting MRR", x=dm.index, y=dm.starting_mrr, marker_color=COLORS["starting_mrr"]
        )
    )
    for col in ["new", "expansion", "reactivation"]:
        if dm[col].any():
            fig.add_trace(
                go.Bar(name=col.title(), x=dm.index, y=dm[col], marker_color=COLORS[col])
            )
    for col in ["contraction", "churn"]:
        if dm[col].any():
            fig.add_trace(
                go.Bar(name=col.title(), x=dm.index, y=dm[col], marker_color=COLORS[col])
            )
    fig.add_trace(
        go.Scatter(
            name="Ending MRR",
            x=dm.index,
            y=dm.ending_mrr,
            mode="lines+markers+text",
            line={"color": "black", "width": 2},
            marker={"size": 8},
            text=[f"${v:,.0f}" for v in dm.ending_mrr],
            textposition="top center",
        )
    )
    fig.update_layout(
        barmode="relative",
        title="Monthly MRR Waterfall",
        yaxis_title="MRR ($)",
        yaxis_tickprefix="$",
        yaxis_tickformat=",",
        legend={"orientation": "h", "y": -0.15},
        height=500,
    )
    return fig


def plot_trend(df: pd.DataFrame) -> go.Figure:
    """MRR trend line over time.

    Args:
        df: DataFrame from :func:`trend`.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.month,
            y=df.ending_mrr,
            mode="lines+markers+text",
            fill="tozeroy",
            line={"color": COLORS["new"], "width": 2.5},
            marker={"size": 8},
            text=[f"${v:,.0f}" for v in df.ending_mrr],
            textposition="top center",
        )
    )
    fig.update_layout(
        title="MRR Over Time",
        yaxis_title="MRR ($)",
        yaxis_tickprefix="$",
        yaxis_tickformat=",",
        yaxis_rangemode="tozero",
    )
    return fig


def plot_stripe_status_breakdown(df: pd.DataFrame) -> go.Figure:
    """Subscription count pie + MRR-by-status bar.

    Args:
        df: DataFrame from :func:`stripe_status_breakdown`.
    """
    from plotly.subplots import make_subplots

    colors = [COLORS.get(s, COLORS["grey"]) for s in df.status]

    fig = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "domain"}, {"type": "xy"}]],
        subplot_titles=["Subscriptions by Status", "MRR by Status"],
    )
    fig.add_trace(
        go.Pie(labels=df.status, values=df["count"], marker_colors=colors),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=df.status,
            y=df.mrr,
            marker_color=colors,
            text=[f"${v:,.2f}" for v in df.mrr],
            textposition="outside",
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.update_yaxes(title_text="MRR ($)", tickprefix="$", tickformat=",", row=1, col=2)
    fig.update_layout(height=450)
    return fig
