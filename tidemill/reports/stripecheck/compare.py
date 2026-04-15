"""Side-by-side comparison of Tidemill metrics with Stripe ground truth.

Each function queries both sources and returns a structured dict (or
DataFrame) showing the values from each side plus the delta, making it
easy to spot divergences at a glance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from tidemill.reports.stripecheck.stripe_metrics import active_mrr, churn_rates, cohort_retention

if TYPE_CHECKING:
    from tidemill.reports.stripecheck.stripe_data import StripeData
    from tidemill.reports.stripecheck.tidemill_client import TidemillClient


def mrr(
    tm: TidemillClient,
    sd: StripeData,
    at: str | None = None,
) -> dict[str, Any]:
    """Compare current MRR: Tidemill vs Stripe active subscriptions.

    Args:
        tm: Tidemill API client.
        sd: Stripe data source.
        at: Optional ISO date string to query MRR at a specific point.

    Returns:
        Dict with ``tidemill`` and ``stripe`` MRR in cents, ``diff``,
        and ``match`` (bool, True when diff == 0).
    """
    tm_mrr = tm.mrr(at=at)
    st_mrr = active_mrr(sd.subscriptions)
    return {
        "tidemill": tm_mrr,
        "stripe": st_mrr,
        "diff": tm_mrr - st_mrr,
        "match": tm_mrr == st_mrr,
    }


def per_subscription_mrr(sd: StripeData) -> pd.DataFrame:
    """Per-subscription MRR table from Stripe.

    Useful for drilling into which subscriptions contribute to a mismatch.

    Args:
        sd: Stripe data source.

    Returns:
        DataFrame sorted by ``mrr_cents`` descending.
    """
    cols = ["id", "customer", "status", "mrr_cents", "currency"]
    df = sd.subscriptions[cols].copy()
    df["mrr"] = df.mrr_cents.apply(lambda c: f"${c / 100:,.2f}")
    return df.sort_values("mrr_cents", ascending=False).reset_index(drop=True)


def churn(
    tm: TidemillClient,
    sd: StripeData,
    start: str,
    end: str,
    starting_mrr_cents: int | None = None,
) -> dict[str, Any]:
    """Compare logo and revenue churn rates.

    Args:
        tm: Tidemill API client.
        sd: Stripe data source.
        start: ISO date string for the start of the measurement window.
        end: ISO date string for the end of the measurement window.
        starting_mrr_cents: Override for the Stripe-side revenue churn
            denominator.  When ``None``, the function fetches the Tidemill
            MRR waterfall to use the same starting MRR as Tidemill does,
            ensuring an apples-to-apples comparison.

    Returns:
        Dict with nested ``tidemill`` and ``stripe`` sub-dicts containing
        rates, plus top-level ``logo_match`` and ``revenue_match`` bools.
    """
    tm_logo = tm.churn(start, end, type="logo")
    tm_rev = tm.churn(start, end, type="revenue")

    # Use Tidemill's starting MRR as denominator for Stripe too, so both
    # sides divide by the same base.
    if starting_mrr_cents is None:
        wf = tm.mrr_waterfall(start, end)
        if wf:
            # Find the first month after `start`
            starting_mrr_cents = int(wf[0].get("starting_mrr", 0))

    st = churn_rates(sd.subscriptions, start, end, starting_mrr_cents)

    def _close(a: float | None, b: float | None, tol: float = 1e-6) -> bool:
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return abs(a - b) < tol

    return {
        "tidemill": {"logo_churn": tm_logo, "revenue_churn": tm_rev},
        "stripe": st,
        "logo_match": _close(tm_logo, st["logo_churn"]),
        "revenue_match": _close(tm_rev, st["revenue_churn"]),
    }


def retention(
    tm: TidemillClient,
    sd: StripeData,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Compare Tidemill cohort retention with Stripe ground truth.

    Returns a merged DataFrame with columns from both sources so you can
    inspect per-cell divergences.  If Tidemill returns no data (e.g.
    retention hasn't been seeded yet), only Stripe columns are present.

    Args:
        tm: Tidemill API client.
        sd: Stripe data source.
        start: ISO date string for the start of the calendar range.
        end: ISO date string for the end of the calendar range.

    Returns:
        Merged DataFrame with Tidemill and Stripe retention columns.
    """
    # Stripe side
    stripe_ret = cohort_retention(sd.subscriptions, start, end)
    stripe_activity = stripe_ret.attrs.get("activity", pd.DataFrame())

    stripe_flat = (
        stripe_activity[stripe_activity.active]
        .groupby(["cohort_month", "active_month"])
        .customer.nunique()
        .reset_index()
        .rename(columns={"customer": "stripe_active"})
    )
    stripe_sizes = stripe_activity.groupby("cohort_month").customer.nunique()
    stripe_flat["stripe_cohort_size"] = stripe_flat.cohort_month.map(stripe_sizes)
    stripe_flat["stripe_retention_pct"] = (
        stripe_flat.stripe_active / stripe_flat.stripe_cohort_size * 100
    )

    # Tidemill side
    tm_data = tm.retention(start, end)
    if not tm_data:
        return stripe_flat

    tm_df = pd.DataFrame(tm_data)
    tm_df["retention_pct"] = tm_df["active_count"] / tm_df["cohort_size"] * 100

    merged = tm_df.merge(stripe_flat, on=["cohort_month", "active_month"], how="outer").fillna(0)

    return merged
