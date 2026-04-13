import { useTimeRange } from '@/hooks/useTimeRange'
import { useChurn } from '@/hooks/useMetrics'
import { KPICard } from '@/components/charts/KPICard'
import { TimeRangePicker } from '@/components/controls/TimeRangePicker'
import { formatPercent } from '@/lib/formatters'

export function ChurnReport() {
  const { start, end, interval, setRange } = useTimeRange({ range: 'last_1y' })

  const { data: logoRate, isLoading: logoRateLoading } = useChurn<number | null>({
    start, end, type: 'logo',
  })
  const { data: revRate, isLoading: revRateLoading } = useChurn<number | null>({
    start, end, type: 'revenue',
  })

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Churn</h2>

      <TimeRangePicker
        onSelectRange={(r) => setRange({ range: r })}
        onSelectInterval={(i) => setRange({ interval: i })}
        currentInterval={interval}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          title="Logo Churn Rate"
          value={logoRate != null ? formatPercent(logoRate) : '—'}
          loading={logoRateLoading}
        />
        <KPICard
          title="Revenue Churn Rate"
          value={revRate != null ? formatPercent(revRate) : '—'}
          loading={revRateLoading}
        />
      </div>
    </div>
  )
}
