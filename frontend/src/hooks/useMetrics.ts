import { useQuery, useQueries } from '@tanstack/react-query'
import {
  fetchMRR,
  fetchARR,
  fetchMRRBreakdown,
  fetchMRRWaterfall,
  fetchChurn,
  fetchChurnCustomers,
  fetchChurnRevenueEvents,
  fetchRetention,
  fetchLTV,
  fetchARPU,
  fetchCohortLTV,
  fetchTrials,
  fetchTrialFunnel,
  fetchTrialSeries,
  fetchSummary,
  fetchMetric,
} from '@/api/metrics'
import type { MetricParams } from '@/api/metrics'

const STALE = 60_000

export function useMRR<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'mrr', params], queryFn: () => fetchMRR<T>(params), staleTime: STALE })
}

export function useARR<T = unknown>(params: MetricParams = {}) {
  return useQuery({ queryKey: ['metrics', 'arr', params], queryFn: () => fetchARR<T>(params), staleTime: STALE })
}

export function useMRRBreakdown<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'mrr', 'breakdown', params], queryFn: () => fetchMRRBreakdown<T>(params), staleTime: STALE })
}

export function useMRRWaterfall<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'mrr', 'waterfall', params], queryFn: () => fetchMRRWaterfall<T>(params), staleTime: STALE })
}

export function useChurn<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'churn', params], queryFn: () => fetchChurn<T>(params), staleTime: STALE })
}

export function useChurnCustomers<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'churn', 'customers', params], queryFn: () => fetchChurnCustomers<T>(params), staleTime: STALE })
}

export function useChurnRevenueEvents<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'churn', 'revenue-events', params], queryFn: () => fetchChurnRevenueEvents<T>(params), staleTime: STALE })
}

export function useRetention<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'retention', params], queryFn: () => fetchRetention<T>(params), staleTime: STALE })
}

export function useLTV<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'ltv', params], queryFn: () => fetchLTV<T>(params), staleTime: STALE })
}

export function useARPU<T = unknown>(params: MetricParams = {}) {
  return useQuery({ queryKey: ['metrics', 'arpu', params], queryFn: () => fetchARPU<T>(params), staleTime: STALE })
}

export function useCohortLTV<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'ltv', 'cohort', params], queryFn: () => fetchCohortLTV<T>(params), staleTime: STALE })
}

export function useTrials<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'trials', params], queryFn: () => fetchTrials<T>(params), staleTime: STALE })
}

export function useTrialFunnel<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'trials', 'funnel', params], queryFn: () => fetchTrialFunnel<T>(params), staleTime: STALE })
}

export function useTrialSeries<T = unknown>(params: MetricParams) {
  return useQuery({ queryKey: ['metrics', 'trials', 'series', params], queryFn: () => fetchTrialSeries<T>(params), staleTime: STALE })
}

export function useSummary<T = unknown>() {
  return useQuery({ queryKey: ['metrics', 'summary'], queryFn: () => fetchSummary<T>(), staleTime: STALE })
}

export function useMetric<T = unknown>(endpoint: string, params: MetricParams) {
  return useQuery({
    queryKey: ['metrics', endpoint, params],
    queryFn: () => fetchMetric<T>(endpoint, params),
    staleTime: STALE,
  })
}

export { useQueries }
