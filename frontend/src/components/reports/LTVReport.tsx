import { useTimeRange } from '@/hooks/useTimeRange'
import { useLTV, useMetric } from '@/hooks/useMetrics'
import { KPICard } from '@/components/charts/KPICard'
import { TimeRangePicker } from '@/components/controls/TimeRangePicker'
import { formatCurrency } from '@/lib/formatters'

export function LTVReport() {
  const { start, end, interval, setRange } = useTimeRange({ range: 'last_1y' })

  const { data: ltv, isLoading: ltvLoading } = useLTV<number | null>({ start, end })
  const { data: arpu, isLoading: arpuLoading } = useMetric<number | null>('/api/metrics/ltv/arpu', {})

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Lifetime Value</h2>

      <TimeRangePicker
        onSelectRange={(r) => setRange({ range: r })}
        onSelectInterval={(i) => setRange({ interval: i })}
        currentInterval={interval}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          title="LTV"
          value={ltv != null ? formatCurrency(ltv / 100) : '—'}
          loading={ltvLoading}
        />
        <KPICard
          title="ARPU"
          value={arpu != null ? formatCurrency(arpu / 100) : '—'}
          loading={arpuLoading}
        />
      </div>
    </div>
  )
}
