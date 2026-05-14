import { useMemo, useState } from 'react'
import { Plus, Upload, Eye, Pencil, X, Search } from 'lucide-react'
import {
  useAttributes,
  useAttributeValues,
  useCreateAttribute,
  useCustomerAttributeRows,
  useUpdateAttribute,
  useImportAttributesCsv,
} from '@/hooks/useAttributes'
import type {
  AttributeDefinition,
  AttributeType,
  CsvImportSummary,
} from '@/api/attributes'

type Tab = 'definitions' | 'data'

const TYPE_OPTIONS: AttributeType[] = ['string', 'number', 'boolean', 'timestamp']

const SOURCE_COLOR: Record<string, string> = {
  api: 'bg-blue-50 text-blue-700 border-blue-200',
  csv: 'bg-amber-50 text-amber-700 border-amber-200',
  stripe: 'bg-purple-50 text-purple-700 border-purple-200',
  quickbooks: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  lago: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  killbill: 'bg-rose-50 text-rose-700 border-rose-200',
}

function badgeClass(source: string) {
  return (
    SOURCE_COLOR[source.toLowerCase()] ??
    'bg-muted text-muted-foreground border-border'
  )
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

/**
 * Manage customer-attribute definitions: list every key the system has
 * observed (from connectors, API writes, and CSV imports), inspect the
 * distinct values that have been ingested, edit human-facing metadata,
 * and create or upload new attributes.
 */
export function AttributesPage() {
  const { data: attributes, isLoading } = useAttributes()
  const [tab, setTab] = useState<Tab>('definitions')
  const [showCreate, setShowCreate] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [editing, setEditing] = useState<AttributeDefinition | null>(null)
  const [viewing, setViewing] = useState<AttributeDefinition | null>(null)

  const sorted = useMemo(
    () => [...(attributes ?? [])].sort((a, b) => a.key.localeCompare(b.key)),
    [attributes],
  )

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Customer Attributes</h2>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Arbitrary key/value metadata attached to customers — discovered
            from connector metadata fan-out, the REST API, or CSV uploads.
            Each key is pinned to a single type the first time it is written;
            use these attributes inside segments to slice any metric.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setShowImport(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-accent"
          >
            <Upload className="w-3.5 h-3.5" /> Import CSV
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="w-3.5 h-3.5" /> New Attribute
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-border">
        <TabButton active={tab === 'definitions'} onClick={() => setTab('definitions')}>
          Definitions
          <span className="ml-1.5 text-xs text-muted-foreground">{sorted.length}</span>
        </TabButton>
        <TabButton active={tab === 'data'} onClick={() => setTab('data')}>
          Imported data
        </TabButton>
      </div>

      {tab === 'data' && (
        <ImportedDataTable attributes={sorted} />
      )}

      {tab === 'definitions' && isLoading && (
        <div className="text-sm text-muted-foreground">Loading…</div>
      )}

      {tab === 'definitions' && !isLoading && sorted.length === 0 && (
        <div className="text-center border border-dashed border-border rounded-lg py-10 text-sm text-muted-foreground">
          No attributes yet. Create one above or import a CSV to get started.
        </div>
      )}

      {tab === 'definitions' && sorted.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted">
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">Key</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">Label</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">Type</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">Source</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">Description</th>
                <th className="text-left px-4 py-2 font-medium text-muted-foreground">Updated</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((a) => (
                <tr key={a.key} className="border-t border-border align-top">
                  <td className="px-4 py-2 font-mono text-xs">{a.key}</td>
                  <td className="px-4 py-2">{a.label || <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-4 py-2">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                      {a.type}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${badgeClass(a.source)}`}>
                      {a.source}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground max-w-[24rem]">
                    {a.description || <span className="italic">No description</span>}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground whitespace-nowrap">
                    {formatDate(a.updated_at)}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => setViewing(a)}
                        title="View imported values"
                        className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setEditing(a)}
                        title="Edit label & description"
                        className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <CreateAttributeDialog onClose={() => setShowCreate(false)} />}
      {showImport && <ImportCsvDialog onClose={() => setShowImport(false)} />}
      {editing && <EditAttributeDialog attribute={editing} onClose={() => setEditing(null)} />}
      {viewing && <ValuesDialog attribute={viewing} onClose={() => setViewing(null)} />}
    </div>
  )
}

// ── Imported data browser ───────────────────────────────────────────────

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 -mb-px border-b-2 text-sm transition-colors ${
        active
          ? 'border-primary text-foreground font-medium'
          : 'border-transparent text-muted-foreground hover:text-foreground'
      }`}
    >
      {children}
    </button>
  )
}

const PAGE_SIZE = 50

function ImportedDataTable({ attributes }: { attributes: AttributeDefinition[] }) {
  const [key, setKey] = useState<string>('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)

  const { data, isLoading, isFetching } = useCustomerAttributeRows({
    key: key || undefined,
    search: search || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  })

  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rows = data?.rows ?? []

  const applySearch = () => {
    setSearch(searchInput.trim())
    setPage(0)
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs flex items-center gap-1.5">
          <span className="text-muted-foreground">Attribute</span>
          <select
            value={key}
            onChange={(e) => {
              setKey(e.target.value)
              setPage(0)
            }}
            className="px-2 py-1 border border-border rounded bg-background"
          >
            <option value="">All keys</option>
            {attributes.map((a) => (
              <option key={a.key} value={a.key}>
                {a.key}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-1.5 ml-auto">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applySearch()}
              placeholder="Search by customer name / email / id"
              className="pl-7 pr-2 py-1 border border-border rounded bg-background text-xs w-72"
            />
          </div>
          <button
            onClick={applySearch}
            className="px-2 py-1 text-xs border border-border rounded hover:bg-accent"
          >
            Search
          </button>
          {(search || key) && (
            <button
              onClick={() => {
                setKey('')
                setSearch('')
                setSearchInput('')
                setPage(0)
              }}
              className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}

      {!isLoading && rows.length === 0 && (
        <div className="text-center border border-dashed border-border rounded-lg py-10 text-sm text-muted-foreground">
          No attribute values have been imported{key ? ` for "${key}"` : ''}
          {search ? ` matching "${search}"` : ''}.
        </div>
      )}

      {rows.length > 0 && (
        <>
          <div className="border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted">
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Customer</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">External ID</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Key</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Value</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Origin</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Updated</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.customer_id}-${r.key}-${i}`} className="border-t border-border">
                    <td className="px-4 py-2">
                      <div className="font-medium">
                        {r.customer_name || <span className="text-muted-foreground italic">unnamed</span>}
                      </div>
                      {r.customer_email && (
                        <div className="text-xs text-muted-foreground">{r.customer_email}</div>
                      )}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                      {r.customer_external_id ?? '—'}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">{r.key}</td>
                    <td className="px-4 py-2 font-mono text-xs">{renderValue(r.value)}</td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded border ${badgeClass(r.origin)}`}>
                        {r.origin}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground whitespace-nowrap">
                      {formatDate(r.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div>
              {total.toLocaleString()} row{total === 1 ? '' : 's'} total
              {isFetching && ' · refreshing…'}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-2 py-1 border border-border rounded hover:bg-accent disabled:opacity-40"
              >
                Previous
              </button>
              <span>
                Page {page + 1} / {pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                disabled={page >= pages - 1}
                className="px-2 py-1 border border-border rounded hover:bg-accent disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Dialogs ──────────────────────────────────────────────────────────────

function Dialog({
  title,
  onClose,
  children,
  wide,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
  wide?: boolean
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        className={`bg-background border border-border rounded-lg p-4 ${wide ? 'w-[640px]' : 'w-[480px]'} max-h-[85vh] overflow-y-auto space-y-3`}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

function CreateAttributeDialog({ onClose }: { onClose: () => void }) {
  const [key, setKey] = useState('')
  const [label, setLabel] = useState('')
  const [type, setType] = useState<AttributeType>('string')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const create = useCreateAttribute()

  const submit = async () => {
    if (!key.trim()) {
      setError('Key is required')
      return
    }
    try {
      await create.mutateAsync({
        key: key.trim(),
        type,
        label: label.trim() || null,
        description: description.trim() || null,
      })
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create attribute')
    }
  }

  return (
    <Dialog title="New attribute" onClose={onClose}>
      <Field label="Key">
        <input
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="e.g. plan_tier"
          className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground mt-0.5">
          Lowercase identifier — used in segment expressions and CSV headers.
        </p>
      </Field>
      <Field label="Type">
        <select
          value={type}
          onChange={(e) => setType(e.target.value as AttributeType)}
          className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
        >
          {TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <p className="text-xs text-muted-foreground mt-0.5">
          Pinned on first write — cannot be changed later without dropping
          stored values.
        </p>
      </Field>
      <Field label="Label">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Human-readable name"
          className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
        />
      </Field>
      <Field label="Description">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder="What does this attribute mean? Where does it come from?"
          className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
        />
      </Field>
      {error && <div className="text-xs text-destructive">{error}</div>}
      <DialogFooter
        onCancel={onClose}
        onSubmit={submit}
        submitDisabled={!key.trim() || create.isPending}
        submitLabel={create.isPending ? 'Saving…' : 'Create'}
      />
    </Dialog>
  )
}

function EditAttributeDialog({
  attribute,
  onClose,
}: {
  attribute: AttributeDefinition
  onClose: () => void
}) {
  const [label, setLabel] = useState(attribute.label ?? '')
  const [description, setDescription] = useState(attribute.description ?? '')
  const [error, setError] = useState<string | null>(null)
  const update = useUpdateAttribute()

  const submit = async () => {
    try {
      await update.mutateAsync({
        key: attribute.key,
        body: {
          label: label.trim() || null,
          description: description.trim() || null,
        },
      })
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update attribute')
    }
  }

  return (
    <Dialog title={`Edit ${attribute.key}`} onClose={onClose}>
      <div className="text-xs text-muted-foreground">
        Type <span className="font-mono">{attribute.type}</span> and key are immutable.
      </div>
      <Field label="Label">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
        />
      </Field>
      <Field label="Description">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
        />
      </Field>
      {error && <div className="text-xs text-destructive">{error}</div>}
      <DialogFooter
        onCancel={onClose}
        onSubmit={submit}
        submitDisabled={update.isPending}
        submitLabel={update.isPending ? 'Saving…' : 'Save'}
      />
    </Dialog>
  )
}

function ValuesDialog({
  attribute,
  onClose,
}: {
  attribute: AttributeDefinition
  onClose: () => void
}) {
  const [limit, setLimit] = useState(100)
  const { data, isLoading } = useAttributeValues(attribute.key, limit)
  const values = data?.values ?? []

  return (
    <Dialog title={`Imported values · ${attribute.key}`} onClose={onClose} wide>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>
          Type <span className="font-mono">{attribute.type}</span>
        </span>
        <span>
          Source <span className="font-mono">{attribute.source}</span>
        </span>
        <span className="ml-auto flex items-center gap-1.5">
          <label htmlFor="vals-limit">Limit</label>
          <select
            id="vals-limit"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="px-1.5 py-0.5 border border-border rounded bg-background"
          >
            {[50, 100, 250, 500, 1000].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </span>
      </div>

      {isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}

      {!isLoading && values.length === 0 && (
        <div className="text-sm text-muted-foreground border border-dashed border-border rounded-md py-6 text-center">
          No values have been written for this attribute yet.
        </div>
      )}

      {!isLoading && values.length > 0 && (
        <>
          <div className="text-xs text-muted-foreground">
            Showing {values.length} distinct value{values.length === 1 ? '' : 's'}
            {values.length >= limit ? ' (limit reached — increase to see more)' : ''}.
          </div>
          <div className="border border-border rounded-md max-h-[50vh] overflow-y-auto">
            <table className="w-full text-sm">
              <tbody>
                {values.map((v, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-3 py-1.5 font-mono text-xs">{renderValue(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Dialog>
  )
}

function ImportCsvDialog({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [idColumn, setIdColumn] = useState('customer_id')
  const [idKind, setIdKind] = useState<'id' | 'external' | 'email'>('id')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CsvImportSummary | null>(null)
  const importCsv = useImportAttributesCsv()

  const submit = async () => {
    if (!file) {
      setError('Choose a CSV file')
      return
    }
    setError(null)
    try {
      const r = await importCsv.mutateAsync({ file, id_column: idColumn, id_kind: idKind })
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed')
    }
  }

  return (
    <Dialog title="Import attributes from CSV" onClose={onClose} wide>
      <p className="text-xs text-muted-foreground">
        Upload a CSV whose header row contains an identifier column plus one
        column per attribute. Types are inferred from the first non-empty
        value when the key has never been seen before.
      </p>
      <Field label="CSV file">
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full mt-0.5 text-xs"
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Identifier column">
          <input
            value={idColumn}
            onChange={(e) => setIdColumn(e.target.value)}
            className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background font-mono text-xs"
          />
        </Field>
        <Field label="Identifier kind">
          <select
            value={idKind}
            onChange={(e) => setIdKind(e.target.value as 'id' | 'external' | 'email')}
            className="block w-full mt-0.5 px-2 py-1 border border-border rounded bg-background"
          >
            <option value="id">Internal UUID</option>
            <option value="external">Connector external id</option>
            <option value="email">Email</option>
          </select>
        </Field>
      </div>

      {error && <div className="text-xs text-destructive">{error}</div>}

      {result && (
        <div className="border border-border rounded-md p-3 text-xs space-y-1 bg-muted/40">
          <div>
            <span className="text-muted-foreground">Rows read</span>{' '}
            <span className="font-medium">{result.rows_read}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Rows written</span>{' '}
            <span className="font-medium">{result.rows_upserted}</span>
          </div>
          {result.keys_created.length > 0 && (
            <div>
              <span className="text-muted-foreground">New keys</span>{' '}
              <span className="font-mono">{result.keys_created.join(', ')}</span>
            </div>
          )}
          {result.unknown_customers.length > 0 && (
            <div className="text-amber-700">
              {result.unknown_customers.length} unknown customer
              {result.unknown_customers.length === 1 ? '' : 's'} skipped
            </div>
          )}
        </div>
      )}

      <DialogFooter
        onCancel={onClose}
        onSubmit={submit}
        submitDisabled={!file || importCsv.isPending}
        submitLabel={importCsv.isPending ? 'Uploading…' : 'Upload'}
      />
    </Dialog>
  )
}

// ── Small UI helpers ─────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  )
}

function DialogFooter({
  onCancel,
  onSubmit,
  submitDisabled,
  submitLabel,
}: {
  onCancel: () => void
  onSubmit: () => void
  submitDisabled?: boolean
  submitLabel: string
}) {
  return (
    <div className="flex items-center justify-end gap-2 pt-1">
      <button
        onClick={onCancel}
        className="px-3 py-1 text-sm border border-border rounded hover:bg-accent"
      >
        Cancel
      </button>
      <button
        onClick={onSubmit}
        disabled={submitDisabled}
        className="px-3 py-1 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {submitLabel}
      </button>
    </div>
  )
}

function renderValue(v: unknown): string {
  if (v === null || v === undefined) return '∅'
  if (typeof v === 'boolean') return v ? 'true' : 'false'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
