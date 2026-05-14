import type { TimeSeriesSeries } from '@/components/charts/TimeSeriesChart'
import { COLORWAY } from './colors'
import { formatPeriod } from './formatters'
import { periodStarts } from './periods'
import type { Interval } from './types'

export interface MrrMovementRow {
  period: string
  amount_base: number
  segment_id?: string
  [dim: string]: unknown
}

export interface CumulativeMrrRow {
  date: string
  [series: string]: string | number
}

export type CumulativeMrrGroupBy =
  | { kind: 'dimension'; key: string }
  | { kind: 'segment'; orderedIds: string[]; label?: (id: string) => string }

export interface CumulativeMrrResult {
  data: CumulativeMrrRow[]
  // Set when grouping produced multiple series; one TimeSeriesSeries per line.
  series?: TimeSeriesSeries[]
}

// Cumulatively sum movement rows ({period, amount_base}) into level-MRR
// samples at every period start in [start, end]. The running sum starts at 0
// because callers fetch from the beginning of time so the cumulative total
// equals the MRR level.
//
// When `groupBy` is provided, rows are bucketed by dimension value or by
// `segment_id`, and one series is emitted per bucket so the chart can render
// a separate line per group.
export function cumulativeMrrSeries(
  rows: MrrMovementRow[],
  start: string,
  end: string,
  interval: Interval,
  options: { seriesKey?: string; groupBy?: CumulativeMrrGroupBy } = {},
): CumulativeMrrResult {
  const periods = periodStarts(start, end, interval)
  const seriesKey = options.seriesKey ?? 'mrr'
  const groupBy = options.groupBy

  if (!groupBy) {
    return { data: singleSeries(rows, periods, interval, seriesKey) }
  }

  if (groupBy.kind === 'dimension') {
    return groupedByDimension(rows, periods, interval, groupBy.key)
  }
  return groupedBySegment(rows, periods, interval, groupBy.orderedIds, groupBy.label)
}

function singleSeries(
  rows: MrrMovementRow[],
  periods: string[],
  interval: Interval,
  seriesKey: string,
): CumulativeMrrRow[] {
  const sorted = [...rows].sort((a, b) => a.period.localeCompare(b.period))
  let level = 0
  const cumulative = sorted.map((row) => {
    level += (row.amount_base ?? 0) / 100
    return { iso: row.period.slice(0, 10), mrr: level }
  })
  let idx = 0
  let curLevel = 0
  return periods.map((p) => {
    while (idx < cumulative.length && cumulative[idx].iso <= p) {
      curLevel = cumulative[idx].mrr
      idx++
    }
    return { date: formatPeriod(p, interval), [seriesKey]: curLevel }
  })
}

function samplesPerBucket(
  bucketRows: MrrMovementRow[],
  periods: string[],
): number[] {
  const sorted = [...bucketRows].sort((a, b) => a.period.localeCompare(b.period))
  let level = 0
  const cumulative = sorted.map((row) => {
    level += (row.amount_base ?? 0) / 100
    return { iso: row.period.slice(0, 10), mrr: level }
  })
  let idx = 0
  let curLevel = 0
  return periods.map((p) => {
    while (idx < cumulative.length && cumulative[idx].iso <= p) {
      curLevel = cumulative[idx].mrr
      idx++
    }
    return curLevel
  })
}

function groupedByDimension(
  rows: MrrMovementRow[],
  periods: string[],
  interval: Interval,
  key: string,
): CumulativeMrrResult {
  if (!rows.some((r) => key in r)) {
    // Dimension not actually present in payload — fall back to single line.
    return { data: singleSeries(rows, periods, interval, 'mrr') }
  }
  const byValue = new Map<string, MrrMovementRow[]>()
  for (const r of rows) {
    const v = r[key] == null ? 'Unknown' : String(r[key])
    if (!byValue.has(v)) byValue.set(v, [])
    byValue.get(v)!.push(r)
  }
  const orderedValues = [...byValue.keys()].sort()
  const perValueSamples = new Map<string, number[]>()
  for (const v of orderedValues) {
    perValueSamples.set(v, samplesPerBucket(byValue.get(v) ?? [], periods))
  }
  const series: TimeSeriesSeries[] = orderedValues.map((v, i) => ({
    key: v,
    label: v,
    color: COLORWAY[i % COLORWAY.length],
  }))
  const data = periods.map((p, i) => {
    const row: CumulativeMrrRow = { date: formatPeriod(p, interval) }
    for (const v of orderedValues) {
      row[v] = perValueSamples.get(v)?.[i] ?? 0
    }
    return row
  })
  return { data, series }
}

function groupedBySegment(
  rows: MrrMovementRow[],
  periods: string[],
  interval: Interval,
  compareIds: string[],
  label?: (id: string) => string,
): CumulativeMrrResult {
  const tagged = rows.some((r) => r.segment_id)
  if (!tagged) {
    return { data: singleSeries(rows, periods, interval, 'mrr') }
  }
  const bySegment = new Map<string, MrrMovementRow[]>()
  for (const r of rows) {
    const id = r.segment_id ?? ''
    if (!bySegment.has(id)) bySegment.set(id, [])
    bySegment.get(id)!.push(r)
  }
  const orderedIds = [
    ...compareIds.filter((id) => bySegment.has(id)),
    ...[...bySegment.keys()].filter((id) => !compareIds.includes(id)),
  ]
  const perSegmentSamples = new Map<string, number[]>()
  for (const id of orderedIds) {
    perSegmentSamples.set(id, samplesPerBucket(bySegment.get(id) ?? [], periods))
  }
  const series: TimeSeriesSeries[] = orderedIds.map((id, i) => ({
    key: id,
    label: label?.(id) ?? id,
    color: COLORWAY[i % COLORWAY.length],
  }))
  const data = periods.map((p, i) => {
    const row: CumulativeMrrRow = { date: formatPeriod(p, interval) }
    for (const id of orderedIds) {
      row[id] = perSegmentSamples.get(id)?.[i] ?? 0
    }
    return row
  })
  return { data, series }
}
