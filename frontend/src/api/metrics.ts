import { get } from './client'
import type { Interval } from '@/lib/types'

export interface MetricParams {
  start?: string
  end?: string
  at?: string
  interval?: Interval
  dimensions?: string[]
  filters?: Record<string, string>
  type?: string
  query_type?: string
  // Universe filter (single segment id).
  segment?: string
  // Compare mode (up to 10 segment ids → per-branch rows in the response).
  compare_segments?: string[]
}

function buildQuery(params: MetricParams): string {
  const sp = new URLSearchParams()
  if (params.start) sp.set('start', params.start)
  if (params.end) sp.set('end', params.end)
  if (params.at) sp.set('at', params.at)
  if (params.interval) sp.set('interval', params.interval)
  if (params.type) sp.set('type', params.type)
  if (params.query_type) sp.set('query_type', params.query_type)
  if (params.segment) sp.set('segment', params.segment)
  params.dimensions?.forEach((d) => sp.append('dimensions', d))
  params.compare_segments?.forEach((s) => sp.append('compare_segments', s))
  if (params.filters) {
    for (const [k, v] of Object.entries(params.filters)) {
      sp.append('filter', `${k}:${v}`)
    }
  }
  const qs = sp.toString()
  return qs ? `?${qs}` : ''
}

export function fetchMetric<T>(endpoint: string, params: MetricParams = {}): Promise<T> {
  return get<T>(`${endpoint}${buildQuery(params)}`)
}

export function fetchMRR<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/mrr', params)
}

export function fetchARR<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/arr', params)
}

export function fetchMRRBreakdown<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/mrr/breakdown', params)
}

export function fetchMRRWaterfall<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/mrr/waterfall', params)
}

export function fetchChurn<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/churn', params)
}

export function fetchChurnCustomers<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/churn/customers', params)
}

export function fetchChurnRevenueEvents<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/churn/revenue-events', params)
}

export function fetchRetention<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/retention', params)
}

export function fetchLTV<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/ltv', params)
}

export function fetchARPU<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/ltv/arpu', params)
}

export function fetchCohortLTV<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/ltv/cohort', params)
}

export function fetchTrials<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/trials', params)
}

export function fetchTrialFunnel<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/trials/funnel', params)
}

export function fetchTrialSeries<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/trials/series', params)
}

export function fetchSummary<T>(params: MetricParams = {}): Promise<T> {
  return fetchMetric<T>('/api/metrics/summary', params)
}
