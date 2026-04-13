import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'

const COLORS = ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626', '#06b6d4', '#ec4899']

interface BarBreakdownChartProps {
  data: Array<Record<string, unknown>>
  bars: string[]
  xKey?: string
  formatter?: (v: number) => string
  loading?: boolean
  stacked?: boolean
}

export function BarBreakdownChart({
  data,
  bars,
  xKey = 'date',
  formatter,
  loading,
  stacked,
}: BarBreakdownChartProps) {
  if (loading) {
    return <div className="h-64 flex items-center justify-center text-muted-foreground">Loading...</div>
  }
  if (!data || data.length === 0) {
    return <div className="h-64 flex items-center justify-center text-muted-foreground">No data</div>
  }

  return (
    <ResponsiveContainer width="100%" height={288}>
      <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
        <YAxis width={80} tickFormatter={formatter} tick={{ fontSize: 12 }} />
        <Tooltip formatter={(v) => formatter ? formatter(Number(v)) : v} />
        {bars.length > 1 && <Legend />}
        {bars.map((key, i) => (
          <Bar
            key={key}
            dataKey={key}
            fill={COLORS[i % COLORS.length]}
            stackId={stacked ? 'stack' : undefined}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
