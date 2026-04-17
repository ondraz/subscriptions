import { useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { useTimeRange } from '@/hooks/useTimeRange'
import { useRetention } from '@/hooks/useMetrics'
import { fetchRetention } from '@/api/metrics'
import { KPICard } from '@/components/charts/KPICard'
import { CohortHeatmap } from '@/components/charts/CohortHeatmap'
import { BarBreakdownChart } from '@/components/charts/BarBreakdownChart'
import { ChartContainer } from '@/components/charts/ChartContainer'
import { formatPercent, formatMonthYear } from '@/lib/formatters'
import type { CohortEntry } from '@/lib/types'

interface RawCohortRow {
  cohort_month: string
  active_month: string
  cohort_size: number
  active_count: number
}

function monthDiff(from: string, to: string): number {
  const a = new Date(from)
  const b = new Date(to)
  return (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth())
}

function monthStarts(start: string, end: string): string[] {
  // `end` is the first day AFTER the selected period (exclusive), so iterate
  // with strict `<` to stop before crossing the boundary.
  const out: string[] = []
  const s = new Date(start)
  const e = new Date(end)
  const cur = new Date(s.getFullYear(), s.getMonth(), 1)
  while (cur < e) {
    out.push(
      `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, '0')}-01`,
    )
    cur.setMonth(cur.getMonth() + 1)
  }
  return out
}

export function RetentionReport() {
  const { start, end } = useTimeRange({ range: 'last_1y' })

  const { data: cohortRaw, isLoading: cohortLoading } = useRetention<RawCohortRow[]>({ start, end })
  const { data: nrr, isLoading: nrrLoading } = useRetention<number | null>({ start, end, query_type: 'nrr' })
  const { data: grr, isLoading: grrLoading } = useRetention<number | null>({ start, end, query_type: 'grr' })

  const cohortEntries: CohortEntry[] = Array.isArray(cohortRaw)
    ? cohortRaw.map((row) => ({
        cohort_month: row.cohort_month,
        active_month: row.active_month,
        retention_rate: row.cohort_size > 0 ? row.active_count / row.cohort_size : 0,
        months_since: monthDiff(row.cohort_month, row.active_month),
      }))
    : []

  // Monthly NRR/GRR timeline — mirrors reports.retention.nrr_grr().
  const months = useMemo(() => monthStarts(start, end), [start, end])
  const retQueries = useQueries({
    queries: months.flatMap((m, i) => {
      const next = months[i + 1] ?? end
      return [
        {
          queryKey: ['metrics', 'retention', { start: m, end: next, query_type: 'nrr' }],
          queryFn: () => fetchRetention<number | null>({ start: m, end: next, query_type: 'nrr' }),
          staleTime: 60_000,
        },
        {
          queryKey: ['metrics', 'retention', { start: m, end: next, query_type: 'grr' }],
          queryFn: () => fetchRetention<number | null>({ start: m, end: next, query_type: 'grr' }),
          staleTime: 60_000,
        },
      ]
    }),
  })

  const timelineLoading = retQueries.some((q) => q.isLoading)
  const timelineData = months.slice(0, -1).map((m, i) => ({
    date: formatMonthYear(m),
    NRR: ((retQueries[i * 2]?.data as number | null | undefined) ?? 0) * 100,
    GRR: ((retQueries[i * 2 + 1]?.data as number | null | undefined) ?? 0) * 100,
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Retention</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          title="Net Revenue Retention"
          value={nrr != null ? formatPercent(nrr) : '—'}
          loading={nrrLoading}
        />
        <KPICard
          title="Gross Revenue Retention"
          value={grr != null ? formatPercent(grr) : '—'}
          loading={grrLoading}
        />
      </div>

      <ChartContainer
        title="Monthly Revenue Retention"
        chartConfig={{
          name: 'Monthly Revenue Retention',
          metric: 'retention',
          endpoint: '/api/metrics/retention',
          params: { start, end },
          chartType: 'line',
          timeRangeMode: 'fixed',
        }}
      >
        <BarBreakdownChart
          data={timelineData}
          bars={['NRR', 'GRR']}
          formatter={(v) => `${v.toFixed(0)}%`}
          loading={timelineLoading}
        />
      </ChartContainer>

      <ChartContainer
        title="Cohort Retention"
        chartConfig={{
          name: 'Cohort Retention',
          metric: 'retention',
          endpoint: '/api/metrics/retention',
          params: { start, end },
          chartType: 'cohort_heatmap',
          timeRangeMode: 'fixed',
        }}
      >
        <CohortHeatmap data={cohortEntries} loading={cohortLoading} />
      </ChartContainer>
    </div>
  )
}
