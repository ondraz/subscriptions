// Wire-format helpers shared by metric query strings, dashboard chart
// configs, and the segment builder.  Centralised so the backend's casing
// conventions only need to be encoded in one place.

const CURRENCY_FIELD_RE = /(^|\.)currency$/i

/** True when *field* (a cube dim or `customer.currency` / `attr.currency` etc.)
 * names a currency value that the backend stores uppercase. */
export function isCurrencyField(field: string): boolean {
  return CURRENCY_FIELD_RE.test(field)
}

/** Uppercase currency strings, leave other values alone.  Lists/pairs are
 * walked element-wise so `in (usd, eur)` still normalises. */
export function normalizeFilterValue(field: string, value: unknown): unknown {
  if (!isCurrencyField(field)) return value
  if (typeof value === 'string') return value.toUpperCase()
  if (Array.isArray(value)) {
    return value.map((v) => (typeof v === 'string' ? v.toUpperCase() : v))
  }
  return value
}

/** Apply {@link normalizeFilterValue} to every entry in a `key=value` filter
 * map.  Returns a new object — does not mutate the input. */
export function normalizeFilters(
  filters: Record<string, string> | undefined,
): Record<string, string> | undefined {
  if (!filters) return filters
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(filters)) {
    out[k] = String(normalizeFilterValue(k, v))
  }
  return out
}
