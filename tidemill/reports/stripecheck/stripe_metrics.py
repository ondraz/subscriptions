"""Ground-truth metric computation from raw Stripe data.

These functions replicate the metric calculations that Tidemill performs,
but compute them directly from Stripe API objects.  Comparing the two
reveals any divergence in Tidemill's event-driven pipeline.

How Stripe stores billing amounts
=================================

A Stripe **Price** object defines what a customer pays:

- ``unit_amount`` — price in the smallest currency unit (cents for USD,
  yen for JPY, etc.).  For a $21/month plan this is ``2100``.
- ``recurring.interval`` — the billing cycle: ``"day"``, ``"week"``,
  ``"month"``, or ``"year"``.
- ``recurring.interval_count`` — how many intervals per cycle.
  A quarterly plan is ``interval="month", interval_count=3``.

A **SubscriptionItem** pairs a Price with a ``quantity`` (default 1).
A single subscription can have multiple items (e.g. a base plan plus
per-seat pricing).

MRR normalisation
-----------------

MRR (Monthly Recurring Revenue) normalises every billing interval to a
monthly rate:

+----------+----------------------------------------------+
| Interval | Formula                                      |
+==========+==============================================+
| month    | ``amount / interval_count``                  |
+----------+----------------------------------------------+
| year     | ``amount / (12 * interval_count)``            |
+----------+----------------------------------------------+
| week     | ``amount * 52 / (12 * interval_count)``       |
+----------+----------------------------------------------+
| day      | ``amount * 365 / (12 * interval_count)``      |
+----------+----------------------------------------------+

Where ``amount = unit_amount * quantity``.

All arithmetic stays in integer cents (with ``//`` for month/year and
``int(...)`` for week/day) to avoid floating-point drift.  This matches
Tidemill's convention of storing money as ``bigint`` cents.

Only subscriptions with ``status == "active"`` contribute to current MRR.
Trialing subscriptions are excluded unless the trial has a non-zero charge
(which Stripe doesn't do by default).
"""

from __future__ import annotations

from datetime import UTC

import pandas as pd

# ── Per-subscription MRR ─────────────────────────────────────────────


def subscription_mrr(sub: dict) -> int:
    """Compute the monthly MRR contribution of a single Stripe subscription.

    Iterates over every ``SubscriptionItem`` in the subscription, reads
    the ``Price`` on each item, and normalises to a monthly rate using
    the table in the module docstring.

    Edge cases handled:

    - ``unit_amount`` or ``quantity`` being ``None`` — treated as 0 / 1.
    - Missing ``recurring`` block — treated as monthly with count 1.
    - ``"day"`` interval — normalised via 365/12.

    Args:
        sub: A Stripe Subscription object (as a dict), including its
            nested ``items.data[*].price`` objects.

    Returns:
        MRR in cents.  Always non-negative.
    """
    total = 0
    for item in sub["items"]["data"]:
        price = item["price"]
        qty = item.get("quantity", 1) or 1
        unit_amount = price.get("unit_amount", 0) or 0
        amount = unit_amount * qty

        rec = price.get("recurring") or {}
        interval = rec.get("interval", "month")
        interval_count = rec.get("interval_count", 1) or 1

        if interval == "month":
            total += amount // interval_count
        elif interval == "year":
            total += amount // (12 * interval_count)
        elif interval == "week":
            total += int(amount * 52 / (12 * interval_count))
        elif interval == "day":
            total += int(amount * 365 / (12 * interval_count))
    return total


# ── Aggregate MRR ────────────────────────────────────────────────────


def active_mrr(subs: pd.DataFrame) -> int:
    """Total MRR across all active subscriptions (in cents).

    Args:
        subs: DataFrame with columns ``status`` and ``mrr_cents``
            (as produced by ``StripeData.subscriptions``).
    """
    return int(subs.loc[subs.status == "active", "mrr_cents"].sum())


# ── Churn ────────────────────────────────────────────────────────────


def churn_rates(
    subs: pd.DataFrame,
    start: str,
    end: str,
    starting_mrr_cents: int | None = None,
) -> dict:
    """Compute logo and revenue churn from Stripe subscriptions.

    **Logo churn** measures *customer* attrition::

        logo_churn = customers_fully_churned / customers_active_at_start

    A customer is "active at start" if they had at least one subscription
    created before ``start`` that was not yet canceled by ``start``.
    A customer is "fully churned" if they were active at start but have
    no active subscriptions at ``end``.

    **Revenue churn** measures *MRR* attrition::

        revenue_churn = |churned_MRR| / starting_MRR

    ``churned_MRR`` is the sum of ``mrr_cents`` for subscriptions whose
    ``canceled_at`` falls within ``[start, end)``.

    Args:
        subs: DataFrame from ``StripeData.subscriptions``.
        start: ISO date string for the start of the measurement window.
        end: ISO date string for the end of the measurement window.
        starting_mrr_cents: Override for the MRR denominator in revenue
            churn.  If ``None``, computed as the sum of ``mrr_cents`` for
            subscriptions active at ``start``.

    Returns:
        Dict with keys ``logo_churn``, ``revenue_churn``,
        ``active_at_start``, ``fully_churned``, ``churned_mrr_cents``,
        ``starting_mrr_cents``.  Rates are ``None`` when the denominator
        is zero.
    """
    start_dt = pd.Timestamp(start, tz=UTC)
    end_dt = pd.Timestamp(end, tz=UTC)

    # ── per-customer analysis ────────────────────────────────────
    results: list[dict] = []
    for _cust, grp in subs.groupby("customer"):
        # Was this customer active at period start?
        active_at_start = grp[
            (grp.created_at < start_dt)
            & ((grp.canceled_at.isna()) | (grp.canceled_at >= start_dt))
        ]
        was_active = len(active_at_start) > 0

        # Do they still have any subscription active at period end?
        still_active = grp[
            (grp.created_at < end_dt) & ((grp.canceled_at.isna()) | (grp.canceled_at >= end_dt))
        ]
        has_active_at_end = len(still_active) > 0

        # MRR lost to cancellations during the period
        churned_mrr = int(
            grp.loc[
                (grp.canceled_at.notna())
                & (grp.canceled_at >= start_dt)
                & (grp.canceled_at < end_dt),
                "mrr_cents",
            ].sum()
        )

        results.append(
            {
                "was_active": was_active,
                "fully_churned": was_active and not has_active_at_end,
                "churned_mrr": churned_mrr,
            }
        )

    cust = pd.DataFrame(results)

    n_active = int(cust.was_active.sum())
    n_churned = int(cust.fully_churned.sum())
    lost_mrr = int(cust.loc[cust.was_active, "churned_mrr"].sum())

    if starting_mrr_cents is None:
        # Sum MRR of subscriptions that were active at period start
        at_start = subs[
            (subs.created_at < start_dt)
            & ((subs.canceled_at.isna()) | (subs.canceled_at >= start_dt))
        ]
        starting_mrr_cents = int(at_start.mrr_cents.sum())

    return {
        "logo_churn": n_churned / n_active if n_active else None,
        "revenue_churn": lost_mrr / starting_mrr_cents if starting_mrr_cents else None,
        "active_at_start": n_active,
        "fully_churned": n_churned,
        "churned_mrr_cents": lost_mrr,
        "starting_mrr_cents": starting_mrr_cents,
    }


# ── Cohort Retention ─────────────────────────────────────────────────


def cohort_retention(subs: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Build a cohort retention matrix from Stripe subscriptions.

    1. **Cohort assignment:** each customer is assigned to the month of
       their *earliest* subscription ``created_at``.

    2. **Monthly activity:** a customer is "active" in a given month if
       they have at least one subscription that was created on or before
       that month's end *and* not yet canceled by that month's start.

    3. **Retention rate:** for each (cohort, month_offset) cell::

           retention = active_customers / cohort_size x 100

    Args:
        subs: DataFrame from ``StripeData.subscriptions``.
        start: ISO date string for the start of the calendar range.
        end: ISO date string for the end of the calendar range.

    Returns:
        Retention percentages indexed by cohort month, columns are
        month offsets (0, 1, 2, ...).  Values are 0-100 floats.
        Also attaches ``cohort_sizes`` and ``activity`` on the
        DataFrame's ``attrs`` dict.
    """
    # Strip timezone so .to_period("M") doesn't warn on every row
    subs = subs.copy()
    subs["created_at"] = subs.created_at.dt.tz_localize(None)
    subs["canceled_at"] = subs.canceled_at.dt.tz_localize(None)

    # Build customer-level first-sub date
    first_sub = subs.groupby("customer").created_at.min().reset_index()
    first_sub["cohort_month"] = first_sub.created_at.dt.to_period("M")

    months = pd.period_range(start, end, freq="M")

    records: list[dict] = []
    for _, cust_row in first_sub.iterrows():
        cust_id = cust_row["customer"]
        cohort = cust_row["cohort_month"]
        cust_subs = subs[subs.customer == cust_id]

        for month in months:
            if month < cohort:
                continue

            # Active = has a sub created on or before month end that
            # wasn't canceled before month start
            active = False
            for _, s in cust_subs.iterrows():
                if s.created_at.to_period("M") > month:
                    continue
                if pd.notna(s.canceled_at) and s.canceled_at.to_period("M") <= month:
                    continue
                active = True
                break

            records.append(
                {
                    "customer": cust_id,
                    "cohort_month": str(cohort),
                    "active_month": str(month),
                    "months_since": (month - cohort).n,
                    "active": active,
                }
            )

    df = pd.DataFrame(records)

    cohort_sizes = df.groupby("cohort_month").customer.nunique()
    active_counts = (
        df[df.active]
        .groupby(["cohort_month", "months_since"])
        .customer.nunique()
        .unstack(fill_value=0)
    )
    retention_pct = active_counts.div(cohort_sizes, axis=0) * 100

    # Attach cohort sizes so callers can display them
    retention_pct.attrs["cohort_sizes"] = cohort_sizes
    retention_pct.attrs["activity"] = df

    return retention_pct
