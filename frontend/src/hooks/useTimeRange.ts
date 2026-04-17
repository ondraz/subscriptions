import { useSearchParams } from 'react-router-dom'
import { useMemo, useCallback } from 'react'
import type { Interval, RelativeRange } from '@/lib/types'
import { resolveRelativeRange } from '@/lib/constants'

export interface TimeRange {
  start: string
  end: string
  interval: Interval
}

interface StoredTimeRange {
  range?: RelativeRange
  start?: string
  end?: string
  interval?: Interval
}

// v2 switched `end` to exclusive semantics (first day AFTER the included
// period) so the backend's BETWEEN filter captures the full last day.
const STORAGE_KEY = 'tidemill:timerange:v2'

function loadPersisted(): StoredTimeRange {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as StoredTimeRange) : {}
  } catch {
    return {}
  }
}

function savePersisted(state: StoredTimeRange): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // storage full or disabled — non-fatal
  }
}

export function useTimeRange(defaults?: {
  range?: RelativeRange
  interval?: Interval
}) {
  const [searchParams, setSearchParams] = useSearchParams()

  const range = useMemo((): TimeRange => {
    const persisted = loadPersisted()
    const urlRange = searchParams.get('range') as RelativeRange | null
    const urlStart = searchParams.get('start')
    const urlEnd = searchParams.get('end')
    const urlInterval = searchParams.get('interval') as Interval | null

    // Precedence: URL > localStorage > defaults. URL params are preserved so
    // links stay shareable, but when a user navigates between reports (which
    // have no URL params) localStorage carries the selection forward.
    const interval =
      urlInterval || persisted.interval || defaults?.interval || 'month'

    if (urlStart && urlEnd) {
      return { start: urlStart, end: urlEnd, interval }
    }
    if (urlRange) {
      const { start, end } = resolveRelativeRange(urlRange)
      return { start, end, interval }
    }
    if (persisted.start && persisted.end) {
      return { start: persisted.start, end: persisted.end, interval }
    }
    if (persisted.range) {
      const { start, end } = resolveRelativeRange(persisted.range)
      return { start, end, interval }
    }
    const defaultRange = defaults?.range || 'last_90d'
    const { start: ds, end: de } = resolveRelativeRange(defaultRange)
    return { start: ds, end: de, interval }
  }, [searchParams, defaults?.range, defaults?.interval])

  const setRange = useCallback(
    (update: Partial<{ start: string; end: string; interval: Interval; range: RelativeRange }>) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (update.range) {
          next.set('range', update.range)
          next.delete('start')
          next.delete('end')
        } else {
          if (update.start) next.set('start', update.start)
          if (update.end) next.set('end', update.end)
          if (update.start || update.end) next.delete('range')
        }
        if (update.interval) next.set('interval', update.interval)
        return next
      })

      // Merge into persisted store so the next route sees the same selection.
      const prevStored = loadPersisted()
      const nextStored: StoredTimeRange = { ...prevStored }
      if (update.range) {
        nextStored.range = update.range
        delete nextStored.start
        delete nextStored.end
      } else if (update.start || update.end) {
        if (update.start) nextStored.start = update.start
        if (update.end) nextStored.end = update.end
        delete nextStored.range
      }
      if (update.interval) nextStored.interval = update.interval
      savePersisted(nextStored)
    },
    [setSearchParams],
  )

  return { ...range, setRange }
}
