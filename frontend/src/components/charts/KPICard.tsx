interface KPICardProps {
  title: string
  value: string
  subtitle?: string
  loading?: boolean
}

export function KPICard({ title, value, subtitle, loading }: KPICardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="mt-1 text-2xl font-semibold">
        {loading ? '—' : value}
      </p>
      {subtitle && (
        <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
      )}
    </div>
  )
}
