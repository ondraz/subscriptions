import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { COLORS } from '@/lib/colors'

export interface TimeSeriesSeries {
  key: string
  color: string
  label?: string
}

interface TimeSeriesChartProps {
  data: Array<Record<string, unknown>>
  dataKey?: string
  series?: TimeSeriesSeries[]
  xKey?: string
  formatter?: (v: number) => string
  color?: string
  loading?: boolean
}

export function TimeSeriesChart({
  data,
  dataKey,
  series,
  xKey = 'date',
  formatter,
  color = COLORS.new,
  loading,
}: TimeSeriesChartProps) {
  if (loading) {
    return <div className="h-64 flex items-center justify-center text-muted-foreground">Loading...</div>
  }
  if (!data || data.length === 0) {
    return <div className="h-64 flex items-center justify-center text-muted-foreground">No data</div>
  }

  const lines: TimeSeriesSeries[] =
    series && series.length > 0
      ? series
      : [{ key: dataKey ?? 'value', color, label: dataKey ?? 'value' }]
  const showLegend = lines.length > 1

  return (
    <ResponsiveContainer width="100%" height={288}>
      <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
        <YAxis width={80} tickFormatter={formatter} tick={{ fontSize: 12 }} />
        <Tooltip formatter={(v) => (formatter ? formatter(Number(v)) : v)} />
        {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {lines.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label ?? s.key}
            stroke={s.color}
            strokeWidth={2}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
