import { useState } from 'react'
import {
  useSegments,
  useCreateSegment,
  useUpdateSegment,
  useDeleteSegment,
} from '@/hooks/useSegments'
import { SegmentBuilder, emptySegmentDef } from '@/components/controls/SegmentBuilder'
import type { Segment, SegmentDef } from '@/api/segments'

const METRIC_OPTIONS = ['mrr', 'churn', 'retention', 'ltv', 'trials'] as const
type MetricName = (typeof METRIC_OPTIONS)[number]

/**
 * Workspace-wide segment management page.  Lists all segments and lets
 * users create / edit / delete them.  Segmentation is resolved against a
 * selected metric's primary cube — the same mechanism the metric queries
 * use when the segment is applied as a universe filter or compare branch.
 */
export function SegmentsPage() {
  const { data: segments, isLoading } = useSegments()
  const [editing, setEditing] = useState<Segment | null>(null)
  const [showNew, setShowNew] = useState(false)

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Segments</h2>
        <button
          onClick={() => setShowNew(true)}
          className="px-3 py-1 text-sm rounded bg-primary text-primary-foreground"
        >
          + New segment
        </button>
      </div>

      {isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}

      {segments && segments.length === 0 && !showNew && (
        <div className="text-sm text-muted-foreground">
          No segments yet — create one to start filtering or comparing customer
          groups across metrics.
        </div>
      )}

      <div className="space-y-2">
        {segments?.map((s) => (
          <SegmentRow
            key={s.id}
            segment={s}
            onEdit={() => setEditing(s)}
          />
        ))}
      </div>

      {showNew && (
        <SegmentForm
          initial={null}
          onClose={() => setShowNew(false)}
        />
      )}
      {editing && (
        <SegmentForm
          initial={editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

function SegmentRow({ segment, onEdit }: { segment: Segment; onEdit: () => void }) {
  const del = useDeleteSegment()
  return (
    <div className="flex items-center justify-between border border-border rounded p-3">
      <div>
        <div className="text-sm font-medium">{segment.name}</div>
        {segment.description && (
          <div className="text-xs text-muted-foreground">{segment.description}</div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button onClick={onEdit} className="text-xs underline text-primary">
          Edit
        </button>
        <button
          onClick={() => {
            if (confirm(`Delete segment "${segment.name}"?`)) del.mutate(segment.id)
          }}
          className="text-xs underline text-red-600"
        >
          Delete
        </button>
      </div>
    </div>
  )
}

function SegmentForm({ initial, onClose }: { initial: Segment | null; onClose: () => void }) {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [defn, setDefn] = useState<SegmentDef>(initial?.definition ?? emptySegmentDef())
  const [metric, setMetric] = useState<MetricName>('mrr')
  const create = useCreateSegment()
  const update = useUpdateSegment()

  const submit = async () => {
    if (!name.trim()) return
    if (initial) {
      await update.mutateAsync({
        id: initial.id,
        body: { name, description, definition: defn },
      })
    } else {
      await create.mutateAsync({ name, description, definition: defn })
    }
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-background border border-border rounded-lg p-4 w-[720px] max-h-[85vh] overflow-y-auto space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">{initial ? 'Edit segment' : 'New segment'}</h3>
          <button onClick={onClose} className="text-muted-foreground">
            ×
          </button>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs">
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
            />
          </label>
          <label className="text-xs">
            Description
            <input
              value={description ?? ''}
              onChange={(e) => setDescription(e.target.value)}
              className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
            />
          </label>
          <label className="text-xs">
            Build against metric
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as MetricName)}
              className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
            >
              {METRIC_OPTIONS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        </div>
        <SegmentBuilder metric={metric} value={defn} onChange={setDefn} />
        <div className="flex items-center justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-3 py-1 text-sm border border-border rounded">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!name.trim()}
            className="px-3 py-1 text-sm rounded bg-primary text-primary-foreground disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
