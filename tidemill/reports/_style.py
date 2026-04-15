"""Shared styling constants and Plotly template for reports."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ── Tidemill colour palette ─────────────────────────────────────────
# Warm orange-based palette for financial / SaaS analytics dashboards.

COLORS: dict[str, str] = {
    # MRR movements
    "new": "#16A34A",  # green-600
    "expansion": "#2563EB",  # blue-600
    "contraction": "#EAB308",  # yellow-500
    "churn": "#DC2626",  # red-600
    "reactivation": "#8B5CF6",  # violet-500
    "starting_mrr": "#78716C",  # stone-500
    # subscription status
    "active": "#16A34A",  # green-600
    "canceled": "#DC2626",  # red-600
    "trialing": "#F59E0B",  # amber-500
    "past_due": "#EA580C",  # orange-600
    # trials
    "converted": "#16A34A",  # green-600
    "expired": "#DC2626",  # red-600
    "pending": "#78716C",  # stone-500
    # retention
    "nrr": "#2563EB",  # blue-600
    "grr": "#16A34A",  # green-600
    # churn lines
    "logo_churn": "#DC2626",  # red-600
    "revenue_churn": "#F59E0B",  # amber-500
    # other
    "arpu": "#8B5CF6",  # violet-500
    "grey": "#78716C",  # stone-500
}

# Default colour cycle for multi-series charts.
COLORWAY: list[str] = [
    "#F59E0B",  # amber
    "#2563EB",  # blue
    "#16A34A",  # green
    "#8B5CF6",  # violet
    "#DC2626",  # red
    "#0891B2",  # cyan
    "#DB2777",  # pink
    "#84CC16",  # lime
    "#78716C",  # stone
]

# ── Plotly template ─────────────────────────────────────────────────

tidemill_template = go.layout.Template(
    layout=go.Layout(
        font_family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif",
        font_size=13,
        font_color="#44403C",  # stone-700
        title_font_size=16,
        title_font_color="#1C1917",  # stone-900
        title_x=0.5,
        title_y=0.97,
        colorway=COLORWAY,
        colorscale_sequential=[
            [0.0, "#FFF7ED"],  # orange-50
            [0.25, "#FED7AA"],  # orange-200
            [0.5, "#FB923C"],  # orange-400
            [0.75, "#EA580C"],  # orange-600
            [1.0, "#431407"],  # orange-950
        ],
        colorscale_sequentialminus=[
            [0.0, "#431407"],  # orange-950
            [1.0, "#FFF7ED"],  # orange-50
        ],
        coloraxis_colorbar=dict(outlinewidth=0, ticklen=6, tickwidth=1),
        xaxis=dict(
            showgrid=True,
            gridcolor="#E7E5E4",  # stone-200
            title_standoff=8,
            linecolor="#D6D3D1",  # stone-300
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#E7E5E4",  # stone-200
            title_standoff=8,
            linecolor="#D6D3D1",  # stone-300
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
            font_color="#44403C",  # stone-700
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
