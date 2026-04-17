import { useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { useTimeRange } from '@/hooks/useTimeRange'
import { useLTV, useARPU, useCohortLTV } from '@/hooks/useMetrics'
import { fetchARPU, fetchMRR } from '@/api/metrics'
import { KPICard } from '@/components/charts/KPICard'
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart'
import { BarBreakdownChart } from '@/components/charts/BarBreakdownChart'
import { ChartContainer } from '@/components/charts/ChartContainer'
import { formatCurrency, formatPercent, formatMonthYear } from '@/lib/formatters'
import { COLORS } from '@/lib/colors'
import type { CohortLTVEntry } from '@/lib/types'

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

function nextMonth(iso: string): string {
  const d = new Date(iso)
  d.setMonth(d.getMonth() + 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
}

export function LTVReport() {
  const { start, end } = useTimeRange({ range: 'last_1y' })

  const { data: ltv, isLoading: ltvLoading } = useLTV<number | null>({ start, end })
  const { data: arpu, isLoading: arpuLoading } = useARPU<number | null>()
  const { data: cohortLtv, isLoading: cohortLoading } =
    useCohortLTV<CohortLTVEntry[]>({ start, end })

  // Implied monthly churn = ARPU / LTV (inverse of simple LTV formula).
  const impliedChurn = useMemo(() => {
    if (!arpu || !ltv) return null
    return arpu / ltv
  }, [arpu, ltv])

  // ARPU timeline: one ARPU + MRR call per month.
  // Mirrors reports.ltv.arpu_timeline().
  const months = useMemo(() => monthStarts(start, end), [start, end])
  const arpuQueries = useQueries({
    queries: months.flatMap((m) => {
      const at = nextMonth(m)
      return [
        {
          queryKey: ['metrics', 'arpu', { at }],
          queryFn: () => fetchARPU<number | null>({ at }),
          staleTime: 60_000,
        },
        {
          queryKey: ['metrics', 'mrr', { at }],
          queryFn: () => fetchMRR<number | null>({ at }),
          staleTime: 60_000,
        },
      ]
    }),
  })

  const arpuTimelineLoading = arpuQueries.some((q) => q.isLoading)
  const arpuTimeline = months.map((m, i) => {
    const arpuCents = arpuQueries[i * 2]?.data as number | null | undefined
    return {
      date: formatMonthYear(m),
      arpu: arpuCents != null ? arpuCents / 100 : 0,
    }
  })

  const cohortChartData = (cohortLtv ?? []).map((r) => ({
    date: formatMonthYear(String(r.cohort_month).slice(0, 10)),
    'Avg Revenue': r.avg_revenue_per_customer / 100,
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Lifetime Value</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          title="Simple LTV"
          value={ltv != null ? formatCurrency(ltv / 100) : '—'}
          subtitle="ARPU ÷ monthly churn"
          loading={ltvLoading}
        />
        <KPICard
          title="ARPU"
          value={arpu != null ? formatCurrency(arpu / 100) : '—'}
          loading={arpuLoading}
        />
        <KPICard
          title="Implied Monthly Churn"
          value={impliedChurn != null ? formatPercent(impliedChurn) : '—'}
          loading={ltvLoading || arpuLoading}
        />
      </div>

      <ChartContainer
        title="Monthly ARPU"
        chartConfig={{
          name: 'Monthly ARPU',
          metric: 'ltv',
          endpoint: '/api/metrics/ltv/arpu',
          params: { start, end },
          chartType: 'line',
          timeRangeMode: 'fixed',
        }}
      >
        <TimeSeriesChart
          data={arpuTimeline}
          dataKey="arpu"
          formatter={formatCurrency}
          color={COLORS.arpu}
          loading={arpuTimelineLoading}
        />
      </ChartContainer>

      <ChartContainer
        title="Cohort LTV"
        chartConfig={{
          name: 'Cohort LTV',
          metric: 'ltv',
          endpoint: '/api/metrics/ltv/cohort',
          params: { start, end },
          chartType: 'bar',
          timeRangeMode: 'fixed',
        }}
      >
        <BarBreakdownChart
          data={cohortChartData}
          bars={['Avg Revenue']}
          formatter={formatCurrency}
          loading={cohortLoading}
        />
      </ChartContainer>

      {cohortLtv && cohortLtv.length > 0 && (
        <ChartContainer title="Cohort LTV Detail">
          <CohortLtvTable data={cohortLtv} />
        </ChartContainer>
      )}
    </div>
  )
}

function CohortLtvTable({ data }: { data: CohortLTVEntry[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-muted-foreground border-b border-border">
            <th className="py-1 pr-4 font-medium">Cohort</th>
            <th className="py-1 pr-4 font-medium text-right">Customers</th>
            <th className="py-1 pr-4 font-medium text-right">Avg revenue</th>
            <th className="py-1 pr-4 font-medium text-right">Total revenue</th>
          </tr>
        </thead>
        <tbody>
          {data.map((r) => (
            <tr key={String(r.cohort_month)} className="border-b border-border/50">
              <td className="py-1 pr-4">
                {formatMonthYear(String(r.cohort_month).slice(0, 10))}
              </td>
              <td className="py-1 pr-4 text-right">{r.customer_count}</td>
              <td className="py-1 pr-4 text-right">
                {formatCurrency(r.avg_revenue_per_customer / 100)}
              </td>
              <td className="py-1 pr-4 text-right">
                {formatCurrency(r.total_revenue / 100)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
