"""Foreign exchange rate conversion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession


def normalize_currency(currency: str | None) -> str | None:
    """Return *currency* in the project's canonical form (uppercase ISO 4217).

    Stripe emits lowercase three-letter codes; we store and compare uppercase
    everywhere so filters like ``filter=currency=USD`` always match. ``None``
    and empty strings pass through unchanged so columns that allow NULL stay
    NULL.
    """
    if not currency:
        return currency
    return currency.upper()


class FxRateMissingError(ValueError):
    """No ``fx_rate`` row exists for this currency pair on or before *on_date*.

    Worker consumers catch this specifically and dead-letter the event so
    it can be replayed once the missing rate is backfilled. Subclasses
    :class:`ValueError` for backwards compatibility.
    """

    def __init__(self, currency: str, base_currency: str, on_date: date) -> None:
        super().__init__(f"No FX rate for {currency}/{base_currency} on or before {on_date}")
        self.currency = currency
        self.base_currency = base_currency
        self.on_date = on_date


async def to_base_cents(
    amount_cents: int,
    currency: str,
    on_date: date,
    db: AsyncSession,
    base_currency: str = "USD",
) -> int:
    """Convert *amount_cents* to *base_currency* using the fx_rate table.

    Same-currency is a passthrough (no DB query). Raises
    :class:`FxRateMissingError` when no rate row applies.
    """
    if currency.upper() == base_currency.upper():
        return amount_cents

    result = await db.execute(
        text(
            "SELECT rate FROM fx_rate"
            " WHERE from_currency = :c AND to_currency = :base"
            " AND date <= :d ORDER BY date DESC LIMIT 1"
        ),
        {"c": currency.upper(), "base": base_currency.upper(), "d": on_date},
    )
    rate = result.scalar()
    if rate is None:
        raise FxRateMissingError(currency.upper(), base_currency.upper(), on_date)
    return int(amount_cents * rate)
