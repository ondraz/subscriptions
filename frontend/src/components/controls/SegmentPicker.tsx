import { useSegments } from '@/hooks/useSegments'
import type { Segment } from '@/api/segments'

interface SegmentPickerProps {
  // Selected universe-filter segment id (null/empty → no filter).
  segment: string | null
  onSegmentChange: (id: string | null) => void
  // Selected compare-mode segment ids (empty array → no compare).
  compareSegments: string[]
  onCompareSegmentsChange: (ids: string[]) => void
  // Optional hint to hide one or the other row.
  showFilter?: boolean
  showCompare?: boolean
}

/**
 * Filter + compare segment picker.  Two independent rows (filter is a
 * single-select, compare is a multi-select with a cap of 10) so users can
 * pick either, both, or neither.  Segments are workspace-shared, so this
 * calls useSegments() without any user scoping.
 */
export function SegmentPicker({
  segment,
  onSegmentChange,
  compareSegments,
  onCompareSegmentsChange,
  showFilter = true,
  showCompare = true,
}: SegmentPickerProps) {
  const { data: segments, isLoading } = useSegments()
  if (isLoading) return <div className="text-xs text-muted-foreground">Loading segments…</div>
  const list: Segment[] = segments ?? []
  if (list.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">
        No segments yet. <a className="underline" href="/segments">Create one</a>.
      </div>
    )
  }

  const toggleCompare = (id: string) => {
    if (compareSegments.includes(id)) {
      onCompareSegmentsChange(compareSegments.filter((s) => s !== id))
    } else if (compareSegments.length < 10) {
      onCompareSegmentsChange([...compareSegments, id])
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {showFilter && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground min-w-[60px]">Filter:</span>
          <select
            className="text-xs px-2 py-0.5 border border-border rounded bg-background"
            value={segment ?? ''}
            onChange={(e) => onSegmentChange(e.target.value || null)}
          >
            <option value="">All customers</option>
            {list.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {showCompare && (
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-xs text-muted-foreground mr-1 min-w-[60px]">Compare:</span>
          {list.map((s) => (
            <button
              key={s.id}
              onClick={() => toggleCompare(s.id)}
              disabled={!compareSegments.includes(s.id) && compareSegments.length >= 10}
              className={`px-2 py-0.5 text-xs rounded-full border ${
                compareSegments.includes(s.id)
                  ? 'bg-primary/10 border-primary text-primary'
                  : 'border-border text-muted-foreground hover:border-primary/50 disabled:opacity-30'
              }`}
            >
              {s.name}
            </button>
          ))}
          {compareSegments.length > 0 && (
            <button
              onClick={() => onCompareSegmentsChange([])}
              className="px-2 py-0.5 text-xs rounded-full border border-border text-muted-foreground"
            >
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  )
}
