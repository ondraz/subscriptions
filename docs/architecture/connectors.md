# Connectors

> Webhook translators that turn billing system events into internal events.
> Last updated: March 2026

## Design

A connector is a translator. It receives a webhook from a billing system, maps it to one or more [internal events](events.md), and publishes them to Kafka. That's it — connectors have no database access and no business logic.

```python
from abc import ABC, abstractmethod
from subscriptions.events import Event


class Connector(ABC):
    """Translates billing system webhooks into internal events."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Identifier: 'stripe', 'lago', 'killbill'."""
        ...

    @abstractmethod
    def translate(self, webhook_payload: dict) -> list[Event]:
        """Translate a raw webhook payload into internal events.
        Returns an empty list if the webhook type is not relevant."""
        ...

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature. Override per billing system."""
        return True
```

### Webhook Flow

```
Billing System                Connector              Kafka
     │                            │                     │
     │  POST /webhooks/{source}   │                     │
     ├───────────────────────────►│                     │
     │                            │  verify_signature() │
     │                            │  translate()        │
     │                            │                     │
     │                            │  publish(events)    │
     │                            ├────────────────────►│
     │        200 OK              │                     │
     │◄───────────────────────────┤                     │
```

The webhook endpoint returns 200 immediately after publishing to Kafka. Processing happens asynchronously in consumers.

### Backfill

For initial setup or recovery, connectors also support a pull-based backfill that fetches historical data via API and emits the same internal events:

```python
class Connector(ABC):
    # ... translate() as above ...

    def backfill(self, since: datetime | None = None) -> Iterator[Event]:
        """Pull historical data from the billing system API.
        Yields the same internal events as translate()."""
        raise NotImplementedError
```

## Stripe Connector

### Webhook Translation

| Stripe Webhook | Internal Event(s) | Notes |
|---------------|-------------------|-------|
| `customer.created` | `customer.created` | Direct mapping |
| `customer.updated` | `customer.updated` | |
| `customer.deleted` | `customer.deleted` | |
| `customer.subscription.created` | `subscription.created`, optionally `subscription.trial_started` | If `status=trialing`, also emit trial event |
| `customer.subscription.updated` | Depends on what changed (see below) | Most complex translation |
| `customer.subscription.deleted` | `subscription.churned` | |
| `customer.subscription.trial_will_end` | (ignored, handled via status change) | |
| `invoice.created` | `invoice.created` | |
| `invoice.paid` | `invoice.paid` | |
| `invoice.voided` | `invoice.voided` | |
| `invoice.marked_uncollectible` | `invoice.uncollectible` | |
| `payment_intent.succeeded` | `payment.succeeded` | |
| `payment_intent.payment_failed` | `payment.failed` | |
| `charge.refunded` | `payment.refunded` | |

### Subscription Update Translation

`customer.subscription.updated` is Stripe's catch-all. The connector inspects `previous_attributes` to determine what changed:

```python
def _translate_subscription_updated(self, webhook: dict) -> list[Event]:
    sub = webhook["data"]["object"]
    prev = webhook["data"].get("previous_attributes", {})
    events = []

    # Status change
    if "status" in prev:
        old_status = prev["status"]
        new_status = sub["status"]

        if old_status == "trialing" and new_status == "active":
            events.append(self._make_event("subscription.trial_converted", ...))
            events.append(self._make_event("subscription.activated", ...))
        elif old_status == "trialing" and new_status in ("canceled", "unpaid"):
            events.append(self._make_event("subscription.trial_expired", ...))
        elif new_status == "active" and old_status != "active":
            events.append(self._make_event("subscription.activated", ...))
        elif new_status == "canceled":
            events.append(self._make_event("subscription.canceled", ...))
        elif new_status == "paused":
            events.append(self._make_event("subscription.paused", ...))

    # Plan or quantity change (while active)
    if "items" in prev or "quantity" in prev:
        prev_mrr = self._compute_mrr(prev)
        new_mrr = self._compute_mrr(sub)
        events.append(self._make_event("subscription.changed",
            prev_mrr_cents=prev_mrr, new_mrr_cents=new_mrr, ...))

    return events
```

### MRR Computation

```python
def _compute_mrr(self, subscription: dict) -> int:
    """Compute MRR in cents from a Stripe subscription object."""
    total = 0
    for item in subscription.get("items", {}).get("data", []):
        price = item["price"]
        qty = item.get("quantity", 1)
        amount = price["unit_amount"] * qty
        interval = price["recurring"]["interval"]
        interval_count = price["recurring"]["interval_count"]

        match interval:
            case "month": total += amount // interval_count
            case "year":  total += amount // (12 * interval_count)
            case "week":  total += int(amount * 52 / (12 * interval_count))
            case "day":   total += int(amount * 365 / (12 * interval_count))
    return total
```

## Lago Connector

### Webhook Translation

Lago's webhooks map more directly to our internal events.

| Lago Webhook | Internal Event(s) | Notes |
|-------------|-------------------|-------|
| `customer.created` | `customer.created` | |
| `customer.updated` | `customer.updated` | |
| `subscription.started` | `subscription.created` + `subscription.activated` | Lago starts active |
| `subscription.terminated` | `subscription.churned` | |
| `subscription.trial_ended` | `subscription.trial_converted` or `subscription.trial_expired` | Check if subscription is still active |
| `invoice.created` | `invoice.created` | |
| `invoice.payment_status_updated` | `invoice.paid` or `payment.failed` | Depends on new status |
| `credit_note.created` | `payment.refunded` | Map credit notes to refund events |
| `event.received` | `usage.recorded` | Lago's usage events |

### MRR Computation

```python
def _compute_mrr(self, subscription: dict) -> int:
    plan = subscription["plan"]
    amount = plan["amount_cents"]
    match plan["interval"]:
        case "monthly":     return amount
        case "yearly":      return amount // 12
        case "quarterly":   return amount // 3
        case "semiannual":  return amount // 6
        case "weekly":      return int(amount * 52 / 12)
```

## Kill Bill Connector

### Webhook Translation

Kill Bill fires `ExtBusEvent` objects. The connector maps `eventType`:

| Kill Bill Event Type | Internal Event(s) | Notes |
|---------------------|-------------------|-------|
| `ACCOUNT_CREATION` | `customer.created` | |
| `ACCOUNT_CHANGE` | `customer.updated` | |
| `SUBSCRIPTION_CREATION` | `subscription.created` | |
| `SUBSCRIPTION_PHASE` | `subscription.activated` or `subscription.trial_started` | Depends on `phaseType` |
| `SUBSCRIPTION_CHANGE` | `subscription.changed` | Fetch prev/new plan from API |
| `SUBSCRIPTION_CANCEL` | `subscription.canceled` | |
| `SUBSCRIPTION_EXPIRED` | `subscription.churned` | |
| `SUBSCRIPTION_UNCANCEL` | `subscription.reactivated` | |
| `BUNDLE_PAUSE` | `subscription.paused` (per sub in bundle) | |
| `BUNDLE_RESUME` | `subscription.resumed` (per sub in bundle) | |
| `INVOICE_CREATION` | `invoice.created` | |
| `INVOICE_PAYMENT_SUCCESS` | `invoice.paid` + `payment.succeeded` | |
| `INVOICE_PAYMENT_FAILED` | `payment.failed` | |

### MRR from Analytics Plugin

When Kill Bill's analytics plugin is installed, the connector reads `current_mrr` directly from the `analytics_bundles` table and `prev_mrr`/`next_mrr` from `analytics_subscription_transitions`. This is more accurate than computing from catalog prices.

Fallback: compute from catalog plan price + interval (same approach as Stripe/Lago).

## Connector Registry

```python
from subscriptions.connectors import register, get_connector

@register("stripe")
class StripeConnector(Connector):
    ...

# Usage
connector = get_connector("stripe", config={"api_key": "sk_...", "webhook_secret": "whsec_..."})
events = connector.translate(raw_payload)
```

## Adding a New Connector

1. Create `subscriptions/connectors/myplatform.py`
2. Subclass `Connector`, implement `translate()` and optionally `backfill()`
3. Decorate with `@register("myplatform")`
4. Map each vendor webhook to the appropriate internal events
5. Implement MRR computation for the vendor's subscription/pricing model
