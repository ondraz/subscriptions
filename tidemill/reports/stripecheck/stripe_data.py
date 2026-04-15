"""Fetch and cache Stripe subscription data for comparison.

How Stripe API access works
===========================

In **test/sandbox mode**, Stripe organises customers and subscriptions
under **Test Clocks** (``stripe.test_helpers.TestClock``).  A Test Clock
simulates time progression so you can create realistic subscription
lifecycles without waiting for real months to pass.

Fetching all subscriptions requires two nested iterations:

1. List every Test Clock::

       stripe.test_helpers.TestClock.list(limit=100)

2. For each clock, list all subscriptions (including canceled)::

       stripe.Subscription.list(test_clock=clock_id, status="all", limit=100)

In **live mode** (no test clocks), replace step 1 with a single call to
``stripe.Subscription.list(status="all")`` and paginate through all results.

Subscription object structure
-----------------------------

A ``Subscription`` contains:

- ``id`` — unique subscription ID (``sub_...``)
- ``customer`` — Stripe customer ID (``cus_...``)
- ``status`` — lifecycle state, one of:

  - ``trialing`` — in free trial, no charge yet
  - ``active`` — paying, current period valid
  - ``past_due`` — payment failed, retrying
  - ``canceled`` — terminated (``canceled_at`` is set)
  - ``unpaid`` — retries exhausted, still open
  - ``incomplete`` — first payment pending
  - ``incomplete_expired`` — first payment never completed

- ``created`` — Unix timestamp of creation
- ``canceled_at`` — Unix timestamp of cancellation (``None`` if not canceled)
- ``trial_start`` / ``trial_end`` — trial window (``None`` if no trial)
- ``items.data`` — list of ``SubscriptionItem`` objects, each referencing a
  ``Price``.  See ``tidemill.reports.stripecheck.stripe_metrics`` for how prices map to MRR.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import stripe

from tidemill.reports.stripecheck.stripe_metrics import subscription_mrr


class StripeData:
    """Lazy-loading container for Stripe subscription data.

    Hits the Stripe API only on first access and caches the result for
    the lifetime of the object.  Requires ``stripe.api_key`` to be set
    (typically via the ``STRIPE_API_KEY`` env var).

    Attributes:
        subscriptions: One row per subscription with columns: ``id``,
            ``customer``, ``status``, ``mrr_cents``, ``currency``,
            ``created_at``, ``canceled_at``, ``trial_start``, ``trial_end``.
        raw: The underlying Stripe subscription dicts, useful when you
            need fields not surfaced in the DataFrame.
    """

    def __init__(self) -> None:
        self._raw: list[dict] | None = None
        self._df: pd.DataFrame | None = None

    # ── public properties ────────────────────────────────────────────

    @property
    def raw(self) -> list[dict]:
        """Raw Stripe subscription objects (as dicts)."""
        if self._raw is None:
            self._fetch()
        assert self._raw is not None
        return self._raw

    @property
    def subscriptions(self) -> pd.DataFrame:
        """Structured DataFrame of all subscriptions."""
        if self._df is None:
            self._build_df()
        assert self._df is not None
        return self._df

    # ── convenience accessors ────────────────────────────────────────

    @property
    def active(self) -> pd.DataFrame:
        """Only active subscriptions."""
        return self.subscriptions[self.subscriptions.status == "active"]

    @property
    def canceled(self) -> pd.DataFrame:
        """Only canceled subscriptions."""
        return self.subscriptions[self.subscriptions.status == "canceled"]

    def summary(self) -> str:
        """One-line status counts."""
        df = self.subscriptions
        parts = [f"{len(df)} total"]
        for st in ("active", "canceled", "trialing", "past_due", "incomplete_expired"):
            n = (df.status == st).sum()
            if n:
                parts.append(f"{n} {st}")
        return ", ".join(parts)

    # ── internals ────────────────────────────────────────────────────

    def _fetch(self) -> None:
        """Fetch every subscription across all test clocks.

        Stripe's ``auto_paging_iter()`` transparently handles pagination
        so we don't need to manage ``starting_after`` cursors manually.
        """
        clock_ids = [
            c.id for c in stripe.test_helpers.TestClock.list(limit=100).auto_paging_iter()
        ]
        subs: list[dict] = []
        for cid in clock_ids:
            for sub in stripe.Subscription.list(
                limit=100, test_clock=cid, status="all"
            ).auto_paging_iter():
                subs.append(sub.to_dict())
        self._raw = subs

    def _build_df(self) -> None:
        """Transform raw dicts into a structured DataFrame."""
        rows = []
        for s in self.raw:
            rows.append(
                {
                    "id": s["id"],
                    "customer": s["customer"],
                    "status": s["status"],
                    "mrr_cents": subscription_mrr(s),
                    "currency": s.get("currency", "usd"),
                    "created_at": datetime.fromtimestamp(s["created"], tz=UTC),
                    "canceled_at": (
                        datetime.fromtimestamp(s["canceled_at"], tz=UTC)
                        if s.get("canceled_at")
                        else None
                    ),
                    "trial_start": (
                        datetime.fromtimestamp(s["trial_start"], tz=UTC)
                        if s.get("trial_start")
                        else None
                    ),
                    "trial_end": (
                        datetime.fromtimestamp(s["trial_end"], tz=UTC)
                        if s.get("trial_end")
                        else None
                    ),
                }
            )
        self._df = pd.DataFrame(rows)
