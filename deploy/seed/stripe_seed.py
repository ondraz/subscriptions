#!/usr/bin/env python3
"""
Seed Stripe test mode with realistic subscription data using Test Clocks.

Creates customers across multiple plans, advances time through 6 months of
billing cycles, and simulates churn, upgrades, and failed payments — generating
the full set of webhook events our connectors need to handle.

Prerequisites:
    pip install stripe
    export STRIPE_API_KEY=sk_test_...

Usage:
    python stripe_seed.py                  # full seed (15 customers, 6 months)
    python stripe_seed.py --customers 5    # fewer customers
    python stripe_seed.py --months 3       # shorter history
    python stripe_seed.py --cleanup        # delete the test clock and all its data
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

import stripe

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PLANS = [
    {"name": "Starter",      "monthly": 2900,   "annual": 29000},   # $29 / $290
    {"name": "Professional",  "monthly": 7900,   "annual": 79000},   # $79 / $790
    {"name": "Enterprise",    "monthly": 24900,  "annual": 249000},  # $249 / $2490
]

# Customer archetypes — each gets different behavior during simulation
ARCHETYPES = [
    # (name_prefix, plan_index, billing, action)
    # action: "active" | "churn" | "upgrade" | "downgrade" | "fail_payment"
    ("Active Monthly Starter",       0, "month", "active"),
    ("Active Monthly Starter",       0, "month", "active"),
    ("Active Monthly Pro",           1, "month", "active"),
    ("Active Monthly Pro",           1, "month", "active"),
    ("Active Annual Pro",            1, "year",  "active"),
    ("Active Annual Enterprise",     2, "year",  "active"),
    ("Churned Monthly Starter",      0, "month", "churn"),
    ("Churned Monthly Pro",          1, "month", "churn"),
    ("Upgraded Starter→Pro",         0, "month", "upgrade"),
    ("Upgraded Starter→Pro",         0, "month", "upgrade"),
    ("Downgraded Pro→Starter",       1, "month", "downgrade"),
    ("Failed Payment Starter",       0, "month", "fail_payment"),
    ("Failed Payment Pro",           1, "month", "fail_payment"),
    ("Trial Convert Pro",            1, "month", "trial_convert"),
    ("Trial Expire Starter",         0, "month", "trial_expire"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def wait_for_clock(clock_id: str) -> None:
    """Poll until the test clock finishes advancing."""
    while True:
        clock = stripe.test_helpers.TestClock.retrieve(clock_id)
        if clock.status == "ready":
            return
        time.sleep(2)


def create_plans() -> dict:
    """Create products and prices, return mapping."""
    result = {}
    for plan in PLANS:
        product = stripe.Product.create(name=plan["name"])

        monthly_price = stripe.Price.create(
            product=product.id,
            unit_amount=plan["monthly"],
            currency="usd",
            recurring={"interval": "month"},
        )
        annual_price = stripe.Price.create(
            product=product.id,
            unit_amount=plan["annual"],
            currency="usd",
            recurring={"interval": "year"},
        )

        result[plan["name"]] = {
            "product": product,
            "monthly": monthly_price,
            "annual": annual_price,
        }
        print(f"  Plan: {plan['name']} (monthly={monthly_price.id}, annual={annual_price.id})")

    return result


def create_customer(
    name: str,
    index: int,
    clock_id: str,
    *,
    failing_card: bool = False,
) -> stripe.Customer:
    """Create a customer attached to the test clock."""
    customer = stripe.Customer.create(
        name=name,
        email=f"seed-{index}@test.example.com",
        test_clock=clock_id,
        metadata={"seed": "true", "archetype": name},
    )

    if failing_card:
        # Card that always declines
        pm = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": "4000000000000002",
                "exp_month": 12,
                "exp_year": 2034,
                "cvc": "123",
            },
        )
        stripe.PaymentMethod.attach(pm.id, customer=customer.id)
        stripe.Customer.modify(
            customer.id,
            invoice_settings={"default_payment_method": pm.id},
        )
    else:
        stripe.Customer.modify(
            customer.id,
            payment_method="pm_card_visa",
            invoice_settings={"default_payment_method": "pm_card_visa"},
        )

    return customer


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def seed(num_customers: int, num_months: int) -> str:
    """Create seed data. Returns the test clock ID for cleanup."""
    start_date = datetime.utcnow().replace(day=1) - timedelta(days=num_months * 31)
    start_date = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_ts = int(start_date.timestamp())

    print(f"\n{'='*60}")
    print(f"Stripe Test Seed")
    print(f"  Customers:  {num_customers}")
    print(f"  Months:     {num_months}")
    print(f"  Start date: {start_date.date()}")
    print(f"{'='*60}\n")

    # 1. Create plans
    print("Creating plans...")
    plans = create_plans()

    # 2. Create test clock
    print("\nCreating test clock...")
    clock = stripe.test_helpers.TestClock.create(
        frozen_time=start_ts,
        name=f"Seed {start_date.date()} → {datetime.utcnow().date()}",
    )
    print(f"  Clock: {clock.id} (frozen at {start_date.date()})")

    # 3. Create customers and subscriptions
    archetypes = (ARCHETYPES * ((num_customers // len(ARCHETYPES)) + 1))[:num_customers]
    customers = []
    subscriptions = []

    print(f"\nCreating {num_customers} customers and subscriptions...")
    for i, (name, plan_idx, billing, action) in enumerate(archetypes):
        plan_name = PLANS[plan_idx]["name"]
        price = plans[plan_name]["monthly" if billing == "month" else "annual"]

        failing = action == "fail_payment"
        customer = create_customer(f"{name} #{i + 1}", i, clock.id, failing_card=failing)

        trial_end = None
        if action in ("trial_convert", "trial_expire"):
            # 14-day trial
            trial_end = start_ts + 14 * 86400

        sub = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": price.id}],
            trial_end=trial_end if trial_end else "now",
        )

        customers.append({"customer": customer, "action": action, "plan_idx": plan_idx})
        subscriptions.append(sub)
        print(f"  [{action:14s}] {name} #{i + 1} → {plan_name} ({billing})")

    # 4. Advance through months
    print(f"\nAdvancing time through {num_months} months of billing cycles...")
    current = start_date

    for month in range(num_months):
        current += timedelta(days=32)
        current = current.replace(day=1)

        now = datetime.utcnow()
        if current > now:
            current = now

        # Apply mid-month actions in month 2
        if month == 1:
            for i, entry in enumerate(customers):
                action = entry["action"]
                sub = subscriptions[i]

                if action == "churn":
                    stripe.Subscription.modify(sub.id, cancel_at_period_end=True)
                    print(f"  → Marked {entry['customer'].name} for cancellation")

                elif action == "upgrade":
                    new_price = plans["Professional"]["monthly"]
                    stripe.Subscription.modify(
                        sub.id,
                        items=[{"id": sub["items"]["data"][0].id, "price": new_price.id}],
                        proration_behavior="create_prorations",
                    )
                    print(f"  → Upgraded {entry['customer'].name} to Professional")

                elif action == "downgrade":
                    new_price = plans["Starter"]["monthly"]
                    stripe.Subscription.modify(
                        sub.id,
                        items=[{"id": sub["items"]["data"][0].id, "price": new_price.id}],
                        proration_behavior="create_prorations",
                    )
                    print(f"  → Downgraded {entry['customer'].name} to Starter")

        target_ts = int(current.timestamp())
        print(f"  Advancing to {current.date()}...")
        stripe.test_helpers.TestClock.advance(clock.id, frozen_time=target_ts)
        wait_for_clock(clock.id)

    print(f"\n{'='*60}")
    print(f"Seed complete!")
    print(f"  Clock ID: {clock.id}")
    print(f"  Cleanup:  python stripe_seed.py --cleanup {clock.id}")
    print(f"{'='*60}\n")

    return clock.id


def cleanup(clock_id: str) -> None:
    """Delete a test clock and all its resources."""
    print(f"Deleting test clock {clock_id} and all associated resources...")
    stripe.test_helpers.TestClock.delete(clock_id)
    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Stripe test data")
    parser.add_argument("--customers", type=int, default=15, help="Number of customers (default: 15)")
    parser.add_argument("--months", type=int, default=6, help="Months of history (default: 6)")
    parser.add_argument("--cleanup", type=str, metavar="CLOCK_ID", help="Delete a test clock")
    args = parser.parse_args()

    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        print("Error: Set STRIPE_API_KEY environment variable (sk_test_...)", file=sys.stderr)
        sys.exit(1)

    if not api_key.startswith("sk_test_"):
        print("Error: This script only works with test mode keys (sk_test_...)", file=sys.stderr)
        sys.exit(1)

    stripe.api_key = api_key

    if args.cleanup:
        cleanup(args.cleanup)
    else:
        seed(args.customers, args.months)


if __name__ == "__main__":
    main()
