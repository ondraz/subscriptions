import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { COLORS } from '@/lib/colors'

interface TimeSeriesChartProps {
  data: Array<Record<string, unknown>>
  dataKey: string
  xKey?: string
  formatter?: (v: number) => string
  color?: string
  loading?: boolean
}

export function TimeSeriesChart({
  data,
  dataKey,
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

  return (
    <ResponsiveContainer width="100%" height={288}>
      <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
        <YAxis width={80} tickFormatter={formatter} tick={{ fontSize: 12 }} />
        <Tooltip formatter={(v) => formatter ? formatter(Number(v)) : v} />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2}
          dot={{ r: 4 }}
          activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
