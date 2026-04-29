import { useState } from 'react'
import type { Condition, Group, SegmentDef, SegmentOp } from '@/api/segments'
import { useFields } from '@/hooks/useFields'

const OPS_BY_TYPE: Record<string, SegmentOp[]> = {
  string: ['=', '!=', 'in', 'not in', 'contains', 'not_contains', 'starts_with', 'ends_with', 'is_empty', 'is_not_empty'],
  number: ['=', '!=', '>', '>=', '<', '<=', 'in', 'not in', 'between', 'is_empty', 'is_not_empty'],
  boolean: ['=', '!=', 'is_empty', 'is_not_empty'],
  timestamp: ['=', '!=', '>', '>=', '<', '<=', 'between', 'is_empty', 'is_not_empty'],
  date: ['=', '!=', '>', '>=', '<', '<=', 'between', 'is_empty', 'is_not_empty'],
}

const NO_VALUE_OPS = new Set<SegmentOp>(['is_empty', 'is_not_empty'])
const LIST_OPS = new Set<SegmentOp>(['in', 'not in'])
const PAIR_OPS = new Set<SegmentOp>(['between'])

interface SegmentBuilderProps {
  // The metric this segment is scoped to — drives /fields lookup.
  metric: string
  value: SegmentDef
  onChange: (def: SegmentDef) => void
}

/**
 * Rule-builder tree editor.  Nested AND/OR groups with add/remove buttons.
 * Fields come from /api/metrics/{metric}/fields (dimensions + attributes).
 * Operators filter by field type.  Values use free text — no live
 * autocomplete yet (future work: hook up /api/attributes/{key}/values).
 */
export function SegmentBuilder({ metric, value, onChange }: SegmentBuilderProps) {
  const { data: fields, isLoading } = useFields(metric)

  if (isLoading) return <div className="text-xs text-muted-foreground">Loading fields…</div>
  if (!fields) return <div className="text-xs text-red-600">Failed to load fields.</div>

  const allFields = [
    ...fields.dimensions.map((d) => ({ ...d, source: 'cube' })),
    ...fields.attributes.map((a) => ({ ...a, source: 'attribute' })),
  ]

  return (
    <div className="text-xs">
      <GroupEditor
        group={value.root}
        fields={allFields}
        onChange={(root) => onChange({ ...value, root })}
        depth={0}
      />
    </div>
  )
}

interface FieldLike {
  key: string
  label: string
  type?: string
}

interface GroupEditorProps {
  group: Group
  fields: FieldLike[]
  onChange: (g: Group) => void
  depth: number
}

function GroupEditor({ group, fields, onChange, depth }: GroupEditorProps) {
  const update = (patch: Partial<Group>) => onChange({ ...group, ...patch })
  const updateChild = (i: number, child: Condition | Group) => {
    const next = [...group.conditions]
    next[i] = child
    update({ conditions: next })
  }
  const addCondition = () => {
    const defaultField = fields[0] ?? { key: 'customer.country', label: 'country', type: 'string' }
    update({
      conditions: [
        ...group.conditions,
        { field: defaultField.key, op: '=' as SegmentOp, value: '' },
      ],
    })
  }
  const addGroup = () => {
    update({ conditions: [...group.conditions, { op: 'and', conditions: [] }] })
  }
  const removeChild = (i: number) => {
    update({ conditions: group.conditions.filter((_, j) => j !== i) })
  }

  return (
    <div
      className="border border-border rounded p-2 space-y-2"
      style={{ marginLeft: depth * 12 }}
    >
      <div className="flex items-center gap-2">
        <select
          value={group.op}
          onChange={(e) => update({ op: e.target.value as 'and' | 'or' })}
          className="px-2 py-0.5 border border-border rounded bg-background text-xs"
        >
          <option value="and">AND</option>
          <option value="or">OR</option>
        </select>
        <button onClick={addCondition} className="text-xs underline text-primary">
          + Condition
        </button>
        <button onClick={addGroup} className="text-xs underline text-primary">
          + Group
        </button>
      </div>
      {group.conditions.map((c, i) => (
        <div key={i} className="flex items-start gap-2">
          {'conditions' in c ? (
            <GroupEditor
              group={c}
              fields={fields}
              onChange={(nc) => updateChild(i, nc)}
              depth={depth + 1}
            />
          ) : (
            <ConditionEditor
              cond={c}
              fields={fields}
              onChange={(nc) => updateChild(i, nc)}
            />
          )}
          <button
            onClick={() => removeChild(i)}
            className="text-xs text-muted-foreground hover:text-red-600 px-1"
            aria-label="Remove"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

interface ConditionEditorProps {
  cond: Condition
  fields: FieldLike[]
  onChange: (c: Condition) => void
}

function ConditionEditor({ cond, fields, onChange }: ConditionEditorProps) {
  const field = fields.find((f) => f.key === cond.field)
  const fieldType = field?.type ?? 'string'
  const ops = OPS_BY_TYPE[fieldType] ?? OPS_BY_TYPE.string
  const showValue = !NO_VALUE_OPS.has(cond.op)

  return (
    <div className="flex items-center gap-1 flex-wrap flex-1">
      <select
        value={cond.field}
        onChange={(e) => onChange({ ...cond, field: e.target.value })}
        className="px-2 py-0.5 border border-border rounded bg-background text-xs"
      >
        {fields.map((f) => (
          <option key={f.key} value={f.key}>
            {f.label ?? f.key}
          </option>
        ))}
      </select>
      <select
        value={cond.op}
        onChange={(e) => onChange({ ...cond, op: e.target.value as SegmentOp })}
        className="px-2 py-0.5 border border-border rounded bg-background text-xs"
      >
        {ops.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      {showValue && (
        <ValueInput
          op={cond.op}
          value={cond.value}
          type={fieldType}
          onChange={(v) => onChange({ ...cond, value: v })}
        />
      )}
    </div>
  )
}

function ValueInput({
  op,
  value,
  type,
  onChange,
}: {
  op: SegmentOp
  value: unknown
  type: string
  onChange: (v: unknown) => void
}) {
  if (LIST_OPS.has(op)) {
    const csv = Array.isArray(value) ? (value as unknown[]).join(', ') : ''
    return (
      <input
        type="text"
        placeholder="comma-separated"
        value={csv}
        onChange={(e) =>
          onChange(
            e.target.value
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          )
        }
        className="px-2 py-0.5 border border-border rounded bg-background text-xs flex-1"
      />
    )
  }
  if (PAIR_OPS.has(op)) {
    const pair = Array.isArray(value) && value.length === 2 ? (value as [unknown, unknown]) : ['', '']
    return (
      <div className="flex items-center gap-1">
        <input
          type={type === 'timestamp' || type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'}
          value={String(pair[0] ?? '')}
          onChange={(e) => onChange([e.target.value, pair[1]])}
          className="px-2 py-0.5 border border-border rounded bg-background text-xs"
        />
        <span>—</span>
        <input
          type={type === 'timestamp' || type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'}
          value={String(pair[1] ?? '')}
          onChange={(e) => onChange([pair[0], e.target.value])}
          className="px-2 py-0.5 border border-border rounded bg-background text-xs"
        />
      </div>
    )
  }
  if (type === 'boolean') {
    return (
      <select
        value={value === true ? 'true' : value === false ? 'false' : ''}
        onChange={(e) => onChange(e.target.value === 'true')}
        className="px-2 py-0.5 border border-border rounded bg-background text-xs"
      >
        <option value="">—</option>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    )
  }
  return (
    <input
      type={type === 'timestamp' || type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'}
      value={String(value ?? '')}
      onChange={(e) => onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
      className="px-2 py-0.5 border border-border rounded bg-background text-xs flex-1"
    />
  )
}

// Empty starter definition — used by pages that let a user create a new segment.
export function emptySegmentDef(): SegmentDef {
  return { version: 1, root: { op: 'and', conditions: [] } }
}

// Hook for segment-builder state convenience — wraps a useState.
export function useSegmentBuilder(initial?: SegmentDef) {
  const [defn, setDefn] = useState<SegmentDef>(initial ?? emptySegmentDef())
  return { defn, setDefn }
}
