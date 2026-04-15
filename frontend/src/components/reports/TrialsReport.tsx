import { useTimeRange } from '@/hooks/useTimeRange'
import { useMetric } from '@/hooks/useMetrics'
import { KPICard } from '@/components/charts/KPICard'
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart'
import { ChartContainer } from '@/components/charts/ChartContainer'
import { TimeRangePicker } from '@/components/controls/TimeRangePicker'
import { formatPercent, formatNumber } from '@/lib/formatters'
import { COLORS } from '@/lib/colors'

interface TrialFunnel {
  conversion_rate: number | null
  started: number
  converted: number
  expired: number
}

interface TrialSeriesRow {
  period: string
  started: number
  converted: number
  expired: number
  conversion_rate: number | null
}

export function TrialsReport() {
  const { start, end, interval, setRange } = useTimeRange({ range: 'last_1y' })

  const { data: funnel, isLoading: funnelLoading } = useMetric<TrialFunnel>(
    '/api/metrics/trials/funnel', { start, end },
  )
  const { data: rawSeries, isLoading: seriesLoading } = useMetric<TrialSeriesRow[]>(
    '/api/metrics/trials/series', { start, end, interval },
  )

  // Transform series: period → date
  const seriesData = (Array.isArray(rawSeries) ? rawSeries : []).map((row) => ({
    date: String(row.period ?? '').slice(0, 10),
    conversion_rate: row.conversion_rate,
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Trials</h2>

      <TimeRangePicker
        onSelectRange={(r) => setRange({ range: r })}
        onSelectInterval={(i) => setRange({ interval: i })}
        currentInterval={interval}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          title="Conversion Rate"
          value={funnel?.conversion_rate != null ? formatPercent(funnel.conversion_rate) : '—'}
          loading={funnelLoading}
        />
        <KPICard
          title="Started"
          value={funnel?.started != null ? formatNumber(funnel.started) : '—'}
          loading={funnelLoading}
        />
        <KPICard
          title="Converted"
          value={funnel?.converted != null ? formatNumber(funnel.converted) : '—'}
          loading={funnelLoading}
        />
        <KPICard
          title="Expired"
          value={funnel?.expired != null ? formatNumber(funnel.expired) : '—'}
          loading={funnelLoading}
        />
      </div>

      <ChartContainer
        title="Trial Conversion Rate"
        chartConfig={{
          name: 'Trial Conversion Rate',
          metric: 'trials',
          endpoint: '/api/metrics/trials/series',
          params: { start, end, interval },
          chartType: 'line',
          timeRangeMode: 'fixed',
        }}
      >
        <TimeSeriesChart
          data={seriesData}
          dataKey="conversion_rate"
          formatter={formatPercent}
          color={COLORS.arpu}
          loading={seriesLoading}
        />
      </ChartContainer>
    </div>
  )
}
