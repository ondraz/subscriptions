/**
 * Tidemill color palette — shared between all charts, reports, and UI.
 *
 * Mirrors the Python palette in tidemill/reports/_style.py.
 * Ocean/teal-inspired, designed for financial SaaS dashboards.
 */

// ── Semantic colors (metric-specific) ──────────────────────────────

export const COLORS = {
  // MRR movements
  new: '#0D9488',           // teal-600
  expansion: '#2563EB',     // blue-600
  contraction: '#D97706',   // amber-600
  churn: '#DC2626',         // red-600
  reactivation: '#7C3AED',  // violet-600
  startingMrr: '#94A3B8',   // slate-400
  endingMrr: '#0F172A',     // slate-900

  // subscription status
  active: '#0D9488',
  canceled: '#DC2626',
  trialing: '#D97706',
  pastDue: '#EA580C',       // orange-600

  // trials
  converted: '#0D9488',
  expired: '#DC2626',
  pending: '#64748B',       // slate-500

  // retention
  nrr: '#2563EB',
  grr: '#0D9488',

  // churn lines
  logoChurn: '#DC2626',
  revenueChurn: '#EA580C',

  // other
  arpu: '#7C3AED',
  grey: '#94A3B8',
} as const

// ── Default color cycle for multi-series charts ────────────────────

export const COLORWAY = [
  '#0D9488',  // teal
  '#2563EB',  // blue
  '#7C3AED',  // violet
  '#D97706',  // amber
  '#DC2626',  // red
  '#0891B2',  // cyan
  '#DB2777',  // pink
  '#65A30D',  // lime
  '#64748B',  // slate
] as const

// ── MRR movement color map (capitalized keys for chart labels) ─────

export const MRR_COLOR_MAP: Record<string, string> = {
  New: COLORS.new,
  Expansion: COLORS.expansion,
  Reactivation: COLORS.reactivation,
  Contraction: COLORS.contraction,
  Churn: COLORS.churn,
}

// ── Cohort heatmap gradient (teal-based) ───────────────────────────

export function cohortColor(rate: number): string {
  if (rate >= 0.9) return '#CCFBF1'   // teal-100
  if (rate >= 0.7) return '#99F6E4'   // teal-200
  if (rate >= 0.5) return '#FEF08A'   // yellow-200
  if (rate >= 0.3) return '#FED7AA'   // orange-200
  return '#FECACA'                     // red-200
}
