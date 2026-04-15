"""Stripe validation — compare Tidemill analytics with Stripe ground truth.

Provides the data layer for the report functions: a Tidemill REST API
client, a lazy-loading Stripe data fetcher, ground-truth metric
computation from raw Stripe objects, and side-by-side comparison
utilities.

Quick start::

    from tidemill.reports.stripecheck import TidemillClient, StripeData
    from tidemill.reports.stripecheck import compare

    tm = TidemillClient()          # reads TIDEMILL_API / TIDEMILL_API_KEY env vars
    sd = StripeData()              # uses stripe.api_key (set STRIPE_API_KEY)

    result = compare.mrr(tm, sd, at="2026-03-01")
    # {'tidemill': 100933, 'stripe': 100933, 'diff': 0, 'match': True}
"""

from tidemill.reports.stripecheck import compare
from tidemill.reports.stripecheck.stripe_data import StripeData
from tidemill.reports.stripecheck.tidemill_client import TidemillClient

__all__ = [
    "TidemillClient",
    "StripeData",
    "compare",
]
