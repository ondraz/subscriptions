import { useMemo } from 'react'
import { useMetric } from '@/hooks/useMetrics'
import { useSegments } from '@/hooks/useSegments'
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart'
import { BarBreakdownChart } from '@/components/charts/BarBreakdownChart'
import { WaterfallChart } from '@/components/charts/WaterfallChart'
import { CohortHeatmap } from '@/components/charts/CohortHeatmap'
import { KPICard } from '@/components/charts/KPICard'
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  formatPeriod,
  formatMonthYear,
} from '@/lib/formatters'
import { resolveRelativeRange } from '@/lib/constants'
import {
  cumulativeMrrSeries,
  type CumulativeMrrGroupBy,
  type MrrMovementRow,
} from '@/lib/mrrSeries'
import type {
  ChartConfig,
  ChartTransform,
  CohortEntry,
  Interval,
  TrialFunnel,
  WaterfallEntry,
} from '@/lib/types'

interface DynamicChartProps {
  config: ChartConfig
  inherited?: { start: string; end: string; interval?: Interval }
}

const EmptyState = ({ message }: { message: string }) => (
  <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
    {message}
  </div>
)

// Best-guess transform for saved charts predating the transform field.
function inferTransform(config: ChartConfig): ChartTransform | undefined {
  if (config.transform) return config.transform
  switch (config.endpoint) {
    case '/api/metrics/mrr':
      return config.chartType === 'line' || config.chartType === 'area'
        ? 'mrr_cumulative_series'
        : undefined
    case '/api/metrics/mrr/breakdown':
      return 'mrr_breakdown_bars'
    case '/api/metrics/mrr/waterfall':
      return config.chartType === 'waterfall' ? 'waterfall' : 'lost_mrr_bars'
    case '/api/metrics/retention':
      return config.chartType === 'cohort_heatmap' ? 'cohort_heatmap' : 'retention_nrr_grr'
    case '/api/metrics/ltv/cohort':
      return 'cohort_ltv_bars'
    case '/api/metrics/trials/funnel':
      return 'trial_funnel_bars'
    case '/api/metrics/trials/series':
      return config.chartType === 'line' ? 'trial_conversion_line' : 'trial_outcomes_bars'
    default:
      return undefined
  }
}

export function DynamicChart({ config, inherited }: DynamicChartProps) {
  let start = config.params.start
  let end = config.params.end
  let interval = config.params.interval
  if (config.timeRangeMode === 'relative' && config.relativeRange) {
    const resolved = resolveRelativeRange(config.relativeRange)
    start = resolved.start
    end = resolved.end
  } else if (config.timeRangeMode === 'inherit' && inherited) {
    start = inherited.start
    end = inherited.end
    if (inherited.interval) interval = inherited.interval
  }

  const transform = inferTransform(config)

  // Cumulative MRR needs movements from the beginning of time so the running
  // sum equals the level inside [start, end].
  const fetchStart = transform === 'mrr_cumulative_series' ? '2000-01-01' : start

  const params = {
    ...config.params,
    start: fetchStart,
    end,
    interval,
    dimensions: config.dimensions,
    filters: config.filters,
    segment: config.segment,
    compare_segments: config.compareSegments,
  }

  const { data, isLoading } = useMetric(config.endpoint, params)
  const { data: segmentDefs } = useSegments()
  const segmentNameById = useMemo(() => {
    const m = new Map<string, string>()
    for (const s of segmentDefs ?? []) m.set(s.id, s.name)
    return m
  }, [segmentDefs])

  if (transform === 'mrr_cumulative_series') {
    if (!start || !end || !interval) return <EmptyState message="Missing time range" />
    let groupBy: CumulativeMrrGroupBy | undefined
    const dimKey = config.dimensions?.[0]
    if (config.compareSegments && config.compareSegments.length > 0) {
      groupBy = {
        kind: 'segment',
        orderedIds: config.compareSegments,
        label: (id) => segmentNameById.get(id) ?? id,
      }
    } else if (dimKey) {
      groupBy = { kind: 'dimension', key: dimKey }
    }
    const { data: rows, series } = cumulativeMrrSeries(
      (data as MrrMovementRow[]) ?? [],
      start,
      end,
      interval,
      { groupBy },
    )
    return (
      <TimeSeriesChart
        data={rows}
        dataKey={series ? undefined : 'mrr'}
        series={series}
        formatter={formatCurrency}
        loading={isLoading}
      />
    )
  }

  if (transform === 'mrr_breakdown_bars') {
    const raw = (data as Array<Record<string, unknown>>) ?? []
    const rows = raw.map((r) => ({
      type: String(r.movement_type ?? '').replace(/^./, (c) => c.toUpperCase()),
      Amount: (Number(r.amount_base) || 0) / 100,
    }))
    return (
      <BarBreakdownChart
        data={rows}
        bars={['Amount']}
        xKey="type"
        formatter={formatCurrency}
        loading={isLoading}
      />
    )
  }

  if (transform === 'waterfall') {
    return (
      <WaterfallChart
        data={(data as WaterfallEntry[]) ?? []}
        interval={interval}
        loading={isLoading}
      />
    )
  }

  if (transform === 'lost_mrr_bars') {
    const raw = (data as WaterfallEntry[]) ?? []
    const rows = raw.map((r) => ({
      date: interval ? formatPeriod(r.period, interval) : r.period,
      'Lost MRR': Math.abs(Number(r.churn) || 0) / 100,
    }))
    return (
      <BarBreakdownChart
        data={rows}
        bars={['Lost MRR']}
        formatter={formatCurrency}
        loading={isLoading}
      />
    )
  }

  if (transform === 'cohort_heatmap') {
    const raw = (data as Array<{
      cohort_month: string
      active_month: string
      cohort_size: number
      active_count: number
    }>) ?? []
    const entries: CohortEntry[] = raw.map((r) => {
      const from = new Date(r.cohort_month)
      const to = new Date(r.active_month)
      const months_since =
        (to.getFullYear() - from.getFullYear()) * 12 + (to.getMonth() - from.getMonth())
      return {
        cohort_month: r.cohort_month,
        active_month: r.active_month,
        retention_rate: r.cohort_size > 0 ? (r.active_count / r.cohort_size) * 100 : 0,
        months_since,
      }
    })
    return <CohortHeatmap data={entries} loading={isLoading} />
  }

  if (transform === 'cohort_ltv_bars') {
    const raw = (data as Array<{
      cohort_month: string
      avg_revenue_per_customer: number
    }>) ?? []
    const rows = raw.map((r) => ({
      cohort: formatMonthYear(String(r.cohort_month).slice(0, 10)),
      'Avg Revenue': (Number(r.avg_revenue_per_customer) || 0) / 100,
    }))
    return (
      <BarBreakdownChart
        data={rows}
        bars={['Avg Revenue']}
        xKey="cohort"
        formatter={formatCurrency}
        loading={isLoading}
      />
    )
  }

  if (transform === 'trial_funnel_bars') {
    const f = (data as TrialFunnel | null) ?? null
    const rows = f
      ? [
          { stage: 'Started', Count: f.started },
          { stage: 'Converted', Count: f.converted },
          { stage: 'Expired', Count: f.expired },
        ]
      : []
    return (
      <BarBreakdownChart
        data={rows}
        bars={['Count']}
        xKey="stage"
        formatter={formatNumber}
        loading={isLoading}
      />
    )
  }

  if (transform === 'trial_outcomes_bars') {
    const raw = (data as Array<{
      period: string
      started: number
      converted: number
      expired: number
    }>) ?? []
    const rows = raw.map((r) => ({
      date: interval ? formatPeriod(r.period, interval) : r.period,
      Converted: r.converted,
      Expired: r.expired,
      Pending: Math.max(0, r.started - r.converted - r.expired),
    }))
    return (
      <BarBreakdownChart
        data={rows}
        bars={['Converted', 'Expired', 'Pending']}
        formatter={formatNumber}
        loading={isLoading}
        stacked
      />
    )
  }

  if (transform === 'trial_conversion_line') {
    const raw = (data as Array<{ period: string; conversion_rate: number }>) ?? []
    const rows = raw.map((r) => ({
      date: interval ? formatPeriod(r.period, interval) : r.period,
      conversion_rate: r.conversion_rate,
    }))
    return (
      <TimeSeriesChart
        data={rows}
        dataKey="conversion_rate"
        formatter={formatPercent}
        loading={isLoading}
      />
    )
  }

  // Transforms that require per-period fan-out aren't implemented here yet —
  // the live reports compute them via parallel queries. Show a placeholder
  // rather than rendering a misleading chart.
  if (transform === 'churn_timeline' || transform === 'arpu_timeline' || transform === 'retention_nrr_grr') {
    return (
      <EmptyState message="Preview not available — open the report to view this chart." />
    )
  }

  if (config.chartType === 'kpi') {
    return (
      <KPICard
        title={config.name}
        value={data != null ? String(data) : '—'}
        loading={isLoading}
      />
    )
  }

  return <EmptyState message={`Unsupported chart: ${config.endpoint}`} />
}
