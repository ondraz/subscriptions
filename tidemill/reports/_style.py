"""Shared styling constants and Plotly template for reports."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ── Tidemill colour palette ─────────────────────────────────────────
# Ocean-inspired, designed for financial / SaaS analytics dashboards.

COLORS: dict[str, str] = {
    # MRR movements
    "new": "#0D9488",  # teal-600
    "expansion": "#2563EB",  # blue-600
    "contraction": "#D97706",  # amber-600
    "churn": "#DC2626",  # red-600
    "reactivation": "#7C3AED",  # violet-600
    "starting_mrr": "#94A3B8",  # slate-400
    # subscription status
    "active": "#0D9488",
    "canceled": "#DC2626",
    "trialing": "#D97706",
    "past_due": "#EA580C",  # orange-600
    # trials
    "converted": "#0D9488",
    "expired": "#DC2626",
    "pending": "#64748B",  # slate-500
    # retention
    "nrr": "#2563EB",
    "grr": "#0D9488",
    # churn lines
    "logo_churn": "#DC2626",
    "revenue_churn": "#EA580C",
    # other
    "arpu": "#7C3AED",
    "grey": "#94A3B8",
}

# Default colour cycle for multi-series charts.
COLORWAY: list[str] = [
    "#0D9488",  # teal
    "#2563EB",  # blue
    "#7C3AED",  # violet
    "#D97706",  # amber
    "#DC2626",  # red
    "#0891B2",  # cyan
    "#DB2777",  # pink
    "#65A30D",  # lime
    "#64748B",  # slate
]

# ── Plotly template ─────────────────────────────────────────────────

tidemill_template = go.layout.Template(
    layout=go.Layout(
        font_family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif",
        font_size=13,
        font_color="#334155",  # slate-700
        title_font_size=16,
        title_font_color="#0F172A",  # slate-900
        title_x=0.5,
        title_y=0.97,
        colorway=COLORWAY,
        colorscale_sequential=[
            [0.0, "#F0FDFA"],  # teal-50
            [0.25, "#99F6E4"],  # teal-200
            [0.5, "#2DD4BF"],  # teal-400
            [0.75, "#0D9488"],  # teal-600
            [1.0, "#134E4A"],  # teal-900
        ],
        colorscale_sequentialminus=[
            [0.0, "#134E4A"],
            [1.0, "#F0FDFA"],
        ],
        coloraxis_colorbar=dict(outlinewidth=0, ticklen=6, tickwidth=1),
        xaxis=dict(
            showgrid=True,
            gridcolor="#E2E8F0",  # slate-200
            title_standoff=8,
            linecolor="#CBD5E1",  # slate-300
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#E2E8F0",
            title_standoff=8,
            linecolor="#CBD5E1",
            zeroline=False,
        ),
        margin=dict(t=60, b=40, l=60, r=60),
        bargap=0.25,
        width=820,
        height=520,
        legend=dict(
            font_size=12,
            bgcolor="rgba(255,255,255,0)",
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_color="#334155",
        ),
    ),
    data=dict(
        scatter=[dict(type="scatter", line_width=2.5, cliponaxis=False)],
        bar=[dict(type="bar", marker_line_width=0, cliponaxis=False)],
    ),
)


def setup() -> None:
    """Register and activate the Tidemill plotly template."""
    pio.templates["tidemill"] = tidemill_template
    pio.templates.default = "simple_white+tidemill"
    pio.renderers.default = "plotly_mimetype+notebook_connected"
