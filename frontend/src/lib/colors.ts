/**
 * Tidemill color palette — shared between all charts, reports, and UI.
 *
 * Mirrors the Python palette in tidemill/reports/_style.py.
 * Warm orange-based palette designed for financial SaaS dashboards.
 */

// ── Semantic colors (metric-specific) ──────────────────────────────

export const COLORS = {
  // MRR movements
  new: '#16A34A',           // green-600
  expansion: '#2563EB',     // blue-600
  contraction: '#EAB308',   // yellow-500
  churn: '#DC2626',         // red-600
  reactivation: '#8B5CF6',  // violet-500
  startingMrr: '#78716C',   // stone-500
  endingMrr: '#1C1917',     // stone-900

  // subscription status
  active: '#16A34A',        // green-600
  canceled: '#DC2626',      // red-600
  trialing: '#F59E0B',      // amber-500
  pastDue: '#EA580C',       // orange-600

  // trials
  converted: '#16A34A',     // green-600
  expired: '#DC2626',       // red-600
  pending: '#78716C',       // stone-500

  // retention
  nrr: '#2563EB',           // blue-600
  grr: '#16A34A',           // green-600

  // churn lines
  logoChurn: '#DC2626',     // red-600
  revenueChurn: '#F59E0B',  // amber-500

  // other
  arpu: '#8B5CF6',          // violet-500
  grey: '#78716C',          // stone-500
} as const

// ── Default color cycle for multi-series charts ────────────────────

export const COLORWAY = [
  '#F59E0B',  // amber
  '#2563EB',  // blue
  '#16A34A',  // green
  '#8B5CF6',  // violet
  '#DC2626',  // red
  '#0891B2',  // cyan
  '#DB2777',  // pink
  '#84CC16',  // lime
  '#78716C',  // stone
] as const

// ── MRR movement color map (capitalized keys for chart labels) ─────

export const MRR_COLOR_MAP: Record<string, string> = {
  New: COLORS.new,
  Expansion: COLORS.expansion,
  Reactivation: COLORS.reactivation,
  Contraction: COLORS.contraction,
  Churn: COLORS.churn,
}

// ── Cohort heatmap gradient (green → orange → red) ────────────────

export function cohortColor(rate: number): string {
  if (rate >= 0.9) return '#DCFCE7'   // green-100
  if (rate >= 0.7) return '#BBF7D0'   // green-200
  if (rate >= 0.5) return '#FEF08A'   // yellow-200
  if (rate >= 0.3) return '#FED7AA'   // orange-200
  return '#FECACA'                     // red-200
}
