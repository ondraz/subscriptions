import { useTimeRange } from '@/hooks/useTimeRange'
import { useRetention } from '@/hooks/useMetrics'
import { KPICard } from '@/components/charts/KPICard'
import { CohortHeatmap } from '@/components/charts/CohortHeatmap'
import { ChartContainer } from '@/components/charts/ChartContainer'
import { TimeRangePicker } from '@/components/controls/TimeRangePicker'
import { formatPercent } from '@/lib/formatters'
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

export function RetentionReport() {
  const { start, end, interval, setRange } = useTimeRange({ range: 'last_1y' })

  const { data: cohortRaw, isLoading: cohortLoading } = useRetention<RawCohortRow[]>({ start, end })
  const { data: nrr, isLoading: nrrLoading } = useRetention<number | null>({ start, end, query_type: 'nrr' })
  const { data: grr, isLoading: grrLoading } = useRetention<number | null>({ start, end, query_type: 'grr' })

  // Transform raw cohort data: compute retention_rate and months_since
  const cohortEntries: CohortEntry[] = Array.isArray(cohortRaw)
    ? cohortRaw.map((row) => ({
        cohort_month: row.cohort_month,
        active_month: row.active_month,
        retention_rate: row.cohort_size > 0 ? row.active_count / row.cohort_size : 0,
        months_since: monthDiff(row.cohort_month, row.active_month),
      }))
    : []

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Retention</h2>

      <TimeRangePicker
        onSelectRange={(r) => setRange({ range: r })}
        onSelectInterval={(i) => setRange({ interval: i })}
        currentInterval={interval}
      />

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
        title="Cohort Retention"
        chartConfig={{
          name: 'Cohort Retention',
          metric: 'retention',
          endpoint: '/api/metrics/retention',
          params: { start, end, interval },
          chartType: 'cohort_heatmap',
          timeRangeMode: 'fixed',
        }}
      >
        <CohortHeatmap data={cohortEntries} loading={cohortLoading} />
      </ChartContainer>
    </div>
  )
}
