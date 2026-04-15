"""Churn reports — data, style, and plotly chart functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import plotly.graph_objects as go

from tidemill.reports._style import COLORS

if TYPE_CHECKING:
    from tidemill.reports.stripecheck.stripe_data import StripeData
    from tidemill.reports.stripecheck.tidemill_client import TidemillClient


# ── data ─────────────────────────────────────────────────────────────


def stripe_overview(
    tm: TidemillClient,
    sd: StripeData,
    start: str,
    end: str,
) -> dict[str, Any]:
    """Fetch churn comparison between Tidemill and Stripe.

    Args:
        tm: Tidemill API client.
        sd: Stripe data source.
        start: ISO date string for churn window start.
        end: ISO date string for churn window end.

    Returns:
        Dict with ``tidemill``/``stripe`` sub-dicts, match booleans,
        and ``active_mrr_cents``.
    """
    from tidemill.reports.stripecheck.compare import churn as compare_churn

    result = compare_churn(tm, sd, start, end)
    result["active_mrr_cents"] = int(sd.active.mrr_cents.sum())
    return result


def timeline(tm: TidemillClient, start: str, end: str) -> pd.DataFrame:
    """Fetch monthly logo and revenue churn rates.

    Args:
        tm: Tidemill API client.
        start: ISO date for first month of churn measurement.
        end: ISO date for last month boundary.

    Returns:
        DataFrame with ``month``, ``logo_churn``, ``revenue_churn``
        (as decimals, e.g. 0.05 = 5%).
    """
    months = pd.date_range(start, end, freq="MS")
    rows: list[dict[str, Any]] = []
    for i in range(len(months) - 1):
        s = months[i].strftime("%Y-%m-%d")
        e = months[i + 1].strftime("%Y-%m-%d")
        logo = tm.churn(s, e, type="logo")
        revenue = tm.churn(s, e, type="revenue")
        rows.append(
            {
                "month": months[i].strftime("%Y-%m"),
                "logo_churn": float(logo) if logo is not None else None,
                "revenue_churn": float(revenue) if revenue is not None else None,
            }
        )
    return pd.DataFrame(rows)


def monthly_lost_mrr(tm: TidemillClient, start: str, end: str) -> pd.DataFrame:
    """Fetch churned MRR per month from the MRR waterfall.

    Args:
        tm: Tidemill API client.
        start: ISO date string for period start.
        end: ISO date string for period end.

    Returns:
        DataFrame with ``month`` and ``churn_dollars``.
    """
    raw = tm.mrr_waterfall(start, end)
    df = pd.DataFrame(raw)
    df["churn_dollars"] = df["churn"].apply(lambda c: abs(c) / 100)
    return df


# ── style ────────────────────────────────────────────────────────────


def style_stripe_overview(data: dict[str, Any]) -> pd.io.formats.style.Styler:
    """Format churn overview as a styled comparison table.

    Args:
        data: Dict from :func:`stripe_overview`.
    """
    tm = data["tidemill"]
    st = data["stripe"]
    rows = []
    if tm["logo_churn"] is not None and st["logo_churn"] is not None:
        rows.append(
            {
                "Metric": "Logo churn",
                "Tidemill": tm["logo_churn"],
                "Stripe": st["logo_churn"],
                "Match": data["logo_match"],
            }
        )
    if tm["revenue_churn"] is not None and st["revenue_churn"] is not None:
        rows.append(
            {
                "Metric": "Revenue churn",
                "Tidemill": tm["revenue_churn"],
                "Stripe": st["revenue_churn"],
                "Match": data["revenue_match"],
            }
        )
    rows.append(
        {
            "Metric": "Active at start",
            "Tidemill": st["active_at_start"],
            "Stripe": st["active_at_start"],
            "Match": True,
        }
    )
    rows.append(
        {
            "Metric": "Fully churned",
            "Tidemill": st["fully_churned"],
            "Stripe": st["fully_churned"],
            "Match": True,
        }
    )
    df = pd.DataFrame(rows)
    return df.style.format(
        {
            "Tidemill": lambda v: f"{v:.1%}" if isinstance(v, float) else str(v),
            "Stripe": lambda v: f"{v:.1%}" if isinstance(v, float) else str(v),
        }
    ).hide(axis="index")


def style_timeline(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Format monthly churn rates as a styled table.

    Args:
        df: DataFrame from :func:`timeline`.
    """
    return df.set_index("month").style.format(
        {
            "logo_churn": lambda v: f"{v:.1%}" if v is not None else "N/A",
            "revenue_churn": lambda v: f"{v:.1%}" if v is not None else "N/A",
        }
    )


# ── charts ───────────────────────────────────────────────────────────


def plot_stripe_overview(data: dict[str, Any]) -> go.Figure:
    """Customer-churn pie + revenue-impact bar from overview data.

    Args:
        data: Dict returned by :func:`stripe_overview`.
    """
    from plotly.subplots import make_subplots

    st = data["stripe"]
    n_retained = st["active_at_start"] - st["fully_churned"]
    n_churned = st["fully_churned"]
    active_mrr = data["active_mrr_cents"] / 100
    churned_mrr = st["churned_mrr_cents"] / 100

    fig = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "domain"}, {"type": "xy"}]],
        subplot_titles=[
            f"Logo Churn: {n_churned}/{st['active_at_start']} customers",
            "Revenue Impact of Churn",
        ],
    )
    fig.add_trace(
        go.Pie(
            labels=["Retained", "Fully churned"],
            values=[n_retained, n_churned],
            marker_colors=[COLORS["active"], COLORS["churn"]],
            pull=[0, 0.05],
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=["Active MRR", "Churned MRR"],
            y=[active_mrr, churned_mrr],
            marker_color=[COLORS["active"], COLORS["churn"]],
            text=[f"${active_mrr:,.0f}", f"${churned_mrr:,.0f}"],
            textposition="outside",
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.update_yaxes(title_text="MRR ($)", tickprefix="$", tickformat=",", row=1, col=2)
    fig.update_layout(height=450)
    return fig


def plot_timeline(df: pd.DataFrame) -> go.Figure:
    """Monthly logo + revenue churn rate lines.

    Args:
        df: DataFrame from :func:`timeline`.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.month,
            y=df.logo_churn.apply(lambda v: v * 100 if v is not None else None),
            name="Logo Churn",
            mode="lines+markers+text",
            line={"color": COLORS["logo_churn"], "width": 2},
            marker={"size": 8},
            text=[f"{v * 100:.1f}%" if v is not None else "" for v in df.logo_churn],
            textposition="top center",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.month,
            y=df.revenue_churn.apply(lambda v: v * 100 if v is not None else None),
            name="Revenue Churn",
            mode="lines+markers+text",
            line={"color": COLORS["revenue_churn"], "width": 2, "dash": "dash"},
            marker={"size": 8, "symbol": "square"},
            text=[f"{v * 100:.1f}%" if v is not None else "" for v in df.revenue_churn],
            textposition="bottom center",
        )
    )
    fig.update_layout(
        title="Monthly Churn Rate",
        yaxis_title="Churn Rate (%)",
        yaxis_ticksuffix="%",
        yaxis_rangemode="tozero",
    )
    return fig


def plot_monthly_lost_mrr(df: pd.DataFrame) -> go.Figure:
    """Bar chart of churned MRR per month.

    Args:
        df: DataFrame from :func:`monthly_lost_mrr`.
    """
    fig = go.Figure(
        go.Bar(
            x=df.month,
            y=df.churn_dollars,
            marker_color=COLORS["churn"],
            opacity=0.8,
            text=[f"${v:,.0f}" if v > 0 else "" for v in df.churn_dollars],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Monthly Churned MRR",
        yaxis_title="Lost MRR ($)",
        yaxis_tickprefix="$",
        yaxis_tickformat=",",
        yaxis_rangemode="tozero",
    )
    return fig


def stripe_cancellations(
    sd: StripeData,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Subscriptions canceled within the measurement window.

    Args:
        sd: Stripe data source.
        start: ISO date string for window start.
        end: ISO date string for window end.

    Returns:
        DataFrame with canceled subscription details, sorted by date.
    """
    from datetime import UTC

    subs = sd.subscriptions
    start_dt = pd.Timestamp(start, tz=UTC)
    end_dt = pd.Timestamp(end, tz=UTC)
    mask = subs.canceled_at.notna() & (subs.canceled_at >= start_dt) & (subs.canceled_at < end_dt)
    df = subs.loc[mask, ["id", "customer", "mrr_cents", "canceled_at"]].copy()
    df["canceled_month"] = df.canceled_at.dt.strftime("%Y-%m")
    df["mrr"] = df.mrr_cents.apply(lambda c: f"${c / 100:,.2f}")
    return df.sort_values("canceled_at").reset_index(drop=True)


def style_stripe_cancellations(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Format canceled subscriptions as a styled table.

    Args:
        df: DataFrame from :func:`stripe_cancellations`.
    """
    return df[["id", "customer", "canceled_month", "mrr"]].style.hide(axis="index")


def plot_stripe_detail(stripe_churn: dict[str, Any]) -> go.Figure:
    """Stacked retention bars from Stripe churn data.

    Shows retained vs churned customers (left) and MRR (right).

    Args:
        stripe_churn: Dict returned by
            ``stripecheck.stripe_metrics.churn_rates``.
    """
    from plotly.subplots import make_subplots

    n_start = stripe_churn["active_at_start"]
    n_churned = stripe_churn["fully_churned"]
    n_retained = n_start - n_churned
    starting_mrr = stripe_churn["starting_mrr_cents"] / 100
    churned_mrr = stripe_churn["churned_mrr_cents"] / 100
    retained_mrr = starting_mrr - churned_mrr

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=[
            f"Customers ({n_start} at start)",
            f"MRR (${starting_mrr:,.0f} starting)",
        ],
    )
    for col, retained, churned, fmt in [
        (1, n_retained, n_churned, "d"),
        (2, retained_mrr, churned_mrr, ",.0f"),
    ]:
        prefix = "$" if col == 2 else ""
        fig.add_trace(
            go.Bar(
                x=[""],
                y=[retained],
                name="Retained",
                marker_color=COLORS["active"],
                showlegend=(col == 1),
                text=[f"{prefix}{retained:{fmt}}"],
                textposition="inside",
            ),
            row=1,
            col=col,
        )
        fig.add_trace(
            go.Bar(
                x=[""],
                y=[churned],
                name="Churned",
                marker_color=COLORS["churn"],
                showlegend=(col == 1),
                text=[f"{prefix}{churned:{fmt}}"],
                textposition="inside",
            ),
            row=1,
            col=col,
        )
    fig.update_layout(barmode="stack", height=400)
    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_yaxes(title_text="MRR ($)", tickprefix="$", tickformat=",", row=1, col=2)
    return fig
