import { useState } from 'react'
import { RELATIVE_RANGES } from '@/lib/constants'
import type { RelativeRange, Interval } from '@/lib/types'

interface TimeRangePickerProps {
  start: string
  end: string
  onSelectRange: (range: RelativeRange) => void
  onSelectInterval: (interval: Interval) => void
  onSelectDates: (start: string, end: string) => void
  currentInterval: Interval
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

function fmt(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function thisMonth(): { start: string; end: string } {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  return { start: fmt(start), end: fmt(end) }
}

function lastMonth(): { start: string; end: string } {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  const end = new Date(now.getFullYear(), now.getMonth(), 0)
  return { start: fmt(start), end: fmt(end) }
}

function thisWeek(): { start: string; end: string } {
  const now = new Date()
  const day = now.getDay() || 7 // treat Sunday as 7 so Monday is start of week
  const start = new Date(now)
  start.setDate(now.getDate() - (day - 1))
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return { start: fmt(start), end: fmt(end) }
}

export function TimeRangePicker({
  start,
  end,
  onSelectRange,
  onSelectInterval,
  onSelectDates,
  currentInterval,
}: TimeRangePickerProps) {
  const [showCustom, setShowCustom] = useState(false)

  const applyMonth = (isoMonth: string) => {
    // isoMonth is "YYYY-MM" from <input type="month">
    if (!isoMonth) return
    const [y, m] = isoMonth.split('-').map(Number)
    const s = new Date(y, m - 1, 1)
    const e = new Date(y, m, 0)
    onSelectDates(fmt(s), fmt(e))
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div className="flex items-center gap-1 bg-card border border-border rounded-md p-0.5">
        {RELATIVE_RANGES.map((r) => (
          <button
            key={r.value}
            onClick={() => onSelectRange(r.value)}
            className="px-2.5 py-1 text-xs rounded hover:bg-accent text-muted-foreground hover:text-foreground"
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1 bg-card border border-border rounded-md p-0.5">
        <button
          onClick={() => {
            const r = thisMonth()
            onSelectDates(r.start, r.end)
          }}
          className="px-2.5 py-1 text-xs rounded hover:bg-accent text-muted-foreground hover:text-foreground"
        >
          This month
        </button>
        <button
          onClick={() => {
            const r = lastMonth()
            onSelectDates(r.start, r.end)
          }}
          className="px-2.5 py-1 text-xs rounded hover:bg-accent text-muted-foreground hover:text-foreground"
        >
          Last month
        </button>
        <button
          onClick={() => {
            const r = thisWeek()
            onSelectDates(r.start, r.end)
          }}
          className="px-2.5 py-1 text-xs rounded hover:bg-accent text-muted-foreground hover:text-foreground"
        >
          This week
        </button>
      </div>

      <button
        onClick={() => setShowCustom((v) => !v)}
        className={`px-2.5 py-1 text-xs rounded border ${
          showCustom
            ? 'bg-primary/10 border-primary text-primary'
            : 'bg-card border-border text-muted-foreground hover:border-primary/50'
        }`}
      >
        Custom
      </button>

      <div className="flex items-center gap-1 bg-card border border-border rounded-md p-0.5 ml-auto">
        {(['day', 'week', 'month', 'year'] as Interval[]).map((i) => (
          <button
            key={i}
            onClick={() => onSelectInterval(i)}
            className={`px-2.5 py-1 text-xs rounded ${
              currentInterval === i
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            }`}
          >
            {i.charAt(0).toUpperCase() + i.slice(1)}
          </button>
        ))}
      </div>

      {showCustom && (
        <div className="w-full flex items-center gap-2 flex-wrap bg-card border border-border rounded-md p-2">
          <label className="flex items-center gap-1 text-xs text-muted-foreground">
            From
            <input
              type="date"
              value={start}
              onChange={(e) => {
                if (e.target.value) onSelectDates(e.target.value, end)
              }}
              className="bg-background border border-border rounded px-2 py-1 text-xs"
            />
          </label>
          <label className="flex items-center gap-1 text-xs text-muted-foreground">
            To
            <input
              type="date"
              value={end}
              onChange={(e) => {
                if (e.target.value) onSelectDates(start, e.target.value)
              }}
              className="bg-background border border-border rounded px-2 py-1 text-xs"
            />
          </label>
          <label className="flex items-center gap-1 text-xs text-muted-foreground">
            Month
            <input
              type="month"
              value={start.slice(0, 7)}
              onChange={(e) => applyMonth(e.target.value)}
              className="bg-background border border-border rounded px-2 py-1 text-xs"
            />
          </label>
        </div>
      )}
    </div>
  )
}
