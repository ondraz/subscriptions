import { useMemo, useState } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import {
  useSavedCharts,
  useUpdateChart,
  useDeleteChart,
} from '@/hooks/useDashboards'
import { useSegments } from '@/hooks/useSegments'
import { RELATIVE_RANGES } from '@/lib/constants'
import type {
  ChartConfig,
  Interval,
  RelativeRange,
  SavedChart,
  TimeRangeMode,
} from '@/lib/types'

const DIMENSION_OPTIONS: Record<string, string[]> = {
  mrr: ['currency', 'customer_country', 'plan_name'],
  churn: ['cancel_reason', 'customer_country'],
  retention: [],
  ltv: [],
  trials: [],
}

const INTERVALS: Interval[] = ['day', 'week', 'month', 'quarter', 'year']

export function SavedChartsPage() {
  const { data: charts, isLoading } = useSavedCharts()
  const [editing, setEditing] = useState<SavedChart | null>(null)
  const remove = useDeleteChart()

  return (
    <div className="space-y-4 p-4">
      <h2 className="text-lg font-semibold">Saved Charts</h2>

      {isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}

      {charts && charts.length === 0 && (
        <div className="text-sm text-muted-foreground">
          No saved charts yet — open any Report and click the bookmark icon to
          save one.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {charts?.map((c) => (
          <ChartCard
            key={c.id}
            chart={c}
            onEdit={() => setEditing(c)}
            onDelete={() => {
              if (confirm(`Delete "${c.name}"?`)) remove.mutate(c.id)
            }}
          />
        ))}
      </div>

      {editing && <ChartEditor chart={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

function ChartCard({
  chart,
  onEdit,
  onDelete,
}: {
  chart: SavedChart
  onEdit: () => void
  onDelete: () => void
}) {
  const { data: segments } = useSegments()
  const segmentName = (id?: string) =>
    id ? segments?.find((s) => s.id === id)?.name ?? id : null
  const cfg = chart.config

  const timeSummary =
    cfg.timeRangeMode === 'relative' && cfg.relativeRange
      ? RELATIVE_RANGES.find((r) => r.value === cfg.relativeRange)?.label ??
        cfg.relativeRange
      : cfg.timeRangeMode === 'inherit'
        ? 'Inherits from dashboard'
        : cfg.params.start && cfg.params.end
          ? `${cfg.params.start} → ${cfg.params.end}`
          : 'Fixed'

  return (
    <div className="bg-card border border-border rounded-lg p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-medium truncate">{chart.name}</div>
          <div className="text-xs text-muted-foreground capitalize">
            {cfg.metric} · {cfg.chartType.replace('_', ' ')}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onEdit}
            className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
            title="Edit"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onDelete}
            className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-destructive"
            title="Delete"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <dl className="text-xs text-muted-foreground space-y-0.5">
        <Field label="Time">{timeSummary}{cfg.params.interval ? ` · ${cfg.params.interval}` : ''}</Field>
        {cfg.dimensions && cfg.dimensions.length > 0 && (
          <Field label="Group by">{cfg.dimensions.join(', ')}</Field>
        )}
        {cfg.segment && <Field label="Segment">{segmentName(cfg.segment)}</Field>}
        {cfg.compareSegments && cfg.compareSegments.length > 0 && (
          <Field label="Compare">
            {cfg.compareSegments.map((id) => segmentName(id)).join(' vs ')}
          </Field>
        )}
      </dl>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 w-16 text-muted-foreground/80">{label}</dt>
      <dd className="truncate">{children}</dd>
    </div>
  )
}

function ChartEditor({ chart, onClose }: { chart: SavedChart; onClose: () => void }) {
  const update = useUpdateChart()
  const { data: segments } = useSegments()
  const [name, setName] = useState(chart.name)
  const [draft, setDraft] = useState<ChartConfig>(chart.config)

  const dimensionChoices = useMemo(
    () => DIMENSION_OPTIONS[draft.metric] ?? [],
    [draft.metric],
  )

  const setParams = (patch: Partial<ChartConfig['params']>) =>
    setDraft({ ...draft, params: { ...draft.params, ...patch } })

  const toggleDimension = (d: string) => {
    const current = new Set(draft.dimensions ?? [])
    if (current.has(d)) current.delete(d)
    else current.add(d)
    const next = [...current]
    setDraft({ ...draft, dimensions: next.length ? next : undefined })
  }

  const toggleCompare = (id: string) => {
    const current = new Set(draft.compareSegments ?? [])
    if (current.has(id)) current.delete(id)
    else current.add(id)
    const next = [...current]
    setDraft({ ...draft, compareSegments: next.length ? next : undefined })
  }

  const handleSave = () => {
    const trimmed = name.trim()
    if (!trimmed) return
    update.mutate(
      { id: chart.id, name: trimmed, config: { ...draft, name: trimmed } },
      { onSuccess: onClose },
    )
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-lg shadow-lg w-full max-w-xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-border">
          <h3 className="text-sm font-medium">Edit chart</h3>
        </div>
        <div className="p-5 space-y-4">
          <Row label="Name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Row>

          <Row label="Time range">
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={draft.timeRangeMode}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    timeRangeMode: e.target.value as TimeRangeMode,
                  })
                }
                className="border border-border rounded-md px-2 py-1.5 text-sm"
              >
                <option value="fixed">Fixed</option>
                <option value="relative">Relative</option>
                <option value="inherit">Inherit from dashboard</option>
              </select>

              {draft.timeRangeMode === 'relative' && (
                <select
                  value={draft.relativeRange ?? 'last_90d'}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      relativeRange: e.target.value as RelativeRange,
                    })
                  }
                  className="border border-border rounded-md px-2 py-1.5 text-sm"
                >
                  {RELATIVE_RANGES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              )}

              {draft.timeRangeMode === 'fixed' && (
                <>
                  <input
                    type="date"
                    value={draft.params.start ?? ''}
                    onChange={(e) => setParams({ start: e.target.value })}
                    className="border border-border rounded-md px-2 py-1 text-sm"
                  />
                  <span className="text-xs text-muted-foreground">to</span>
                  <input
                    type="date"
                    value={draft.params.end ?? ''}
                    onChange={(e) => setParams({ end: e.target.value })}
                    className="border border-border rounded-md px-2 py-1 text-sm"
                  />
                </>
              )}
            </div>
          </Row>

          <Row label="Interval">
            <select
              value={draft.params.interval ?? ''}
              onChange={(e) =>
                setParams({
                  interval: (e.target.value || undefined) as Interval | undefined,
                })
              }
              className="border border-border rounded-md px-2 py-1.5 text-sm"
            >
              <option value="">— none —</option>
              {INTERVALS.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </Row>

          {dimensionChoices.length > 0 && (
            <Row label="Group by">
              <div className="flex flex-wrap gap-1.5">
                {dimensionChoices.map((d) => {
                  const active = draft.dimensions?.includes(d) ?? false
                  return (
                    <button
                      key={d}
                      type="button"
                      onClick={() => toggleDimension(d)}
                      className={`px-2 py-1 text-xs rounded-md border ${
                        active
                          ? 'bg-primary/10 border-primary text-primary'
                          : 'border-border hover:bg-accent'
                      }`}
                    >
                      {d}
                    </button>
                  )
                })}
              </div>
            </Row>
          )}

          <Row label="Segment">
            <select
              value={draft.segment ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, segment: e.target.value || undefined })
              }
              className="w-full border border-border rounded-md px-2 py-1.5 text-sm"
            >
              <option value="">— none —</option>
              {segments?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Row>

          <Row label="Compare">
            {segments && segments.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {segments.map((s) => {
                  const active = draft.compareSegments?.includes(s.id) ?? false
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => toggleCompare(s.id)}
                      className={`px-2 py-1 text-xs rounded-md border ${
                        active
                          ? 'bg-primary/10 border-primary text-primary'
                          : 'border-border hover:bg-accent'
                      }`}
                    >
                      {s.name}
                    </button>
                  )
                })}
              </div>
            ) : (
              <span className="text-xs text-muted-foreground">No segments defined</span>
            )}
          </Row>

          <Row label="Filters">
            <FiltersEditor
              filters={draft.filters ?? {}}
              onChange={(filters) =>
                setDraft({
                  ...draft,
                  filters: Object.keys(filters).length ? filters : undefined,
                })
              }
            />
          </Row>
        </div>
        <div className="px-5 py-3 border-t border-border flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-accent"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || update.isPending}
            className="px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {update.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] items-start gap-3">
      <label className="text-xs text-muted-foreground pt-1.5">{label}</label>
      <div>{children}</div>
    </div>
  )
}

function FiltersEditor({
  filters,
  onChange,
}: {
  filters: Record<string, string>
  onChange: (next: Record<string, string>) => void
}) {
  const entries = Object.entries(filters)
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')

  const setEntry = (k: string, v: string) => onChange({ ...filters, [k]: v })
  const removeEntry = (k: string) => {
    const next = { ...filters }
    delete next[k]
    onChange(next)
  }
  const addEntry = () => {
    const k = newKey.trim()
    const v = newVal.trim()
    if (!k || !v) return
    setEntry(k, v)
    setNewKey('')
    setNewVal('')
  }

  return (
    <div className="space-y-1.5">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-1.5">
          <input
            type="text"
            value={k}
            readOnly
            className="w-32 border border-border rounded-md px-2 py-1 text-xs bg-muted"
          />
          <span className="text-xs text-muted-foreground">=</span>
          <input
            type="text"
            value={v}
            onChange={(e) => setEntry(k, e.target.value)}
            className="flex-1 border border-border rounded-md px-2 py-1 text-xs"
          />
          <button
            type="button"
            onClick={() => removeEntry(k)}
            className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      ))}
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          placeholder="key"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          className="w-32 border border-border rounded-md px-2 py-1 text-xs"
        />
        <span className="text-xs text-muted-foreground">=</span>
        <input
          type="text"
          placeholder="value"
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
          className="flex-1 border border-border rounded-md px-2 py-1 text-xs"
        />
        <button
          type="button"
          onClick={addEntry}
          disabled={!newKey.trim() || !newVal.trim()}
          className="px-2 py-1 text-xs rounded-md border border-border hover:bg-accent disabled:opacity-50"
        >
          Add
        </button>
      </div>
    </div>
  )
}
