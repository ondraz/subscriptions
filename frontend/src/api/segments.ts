import { get, post, put, del } from './client'

// ── Types ────────────────────────────────────────────────────────────────

export type SegmentOp =
  | '='
  | '!='
  | '>'
  | '>='
  | '<'
  | '<='
  | 'in'
  | 'not in'
  | 'between'
  | 'contains'
  | 'not_contains'
  | 'starts_with'
  | 'ends_with'
  | 'is_empty'
  | 'is_not_empty'

export interface Condition {
  field: string
  op: SegmentOp
  value?: unknown
}

export interface Group {
  op: 'and' | 'or'
  conditions: (Condition | Group)[]
}

export interface SegmentDef {
  version: number
  root: Group
}

export interface Segment {
  id: string
  name: string
  description: string | null
  definition: SegmentDef
  created_by: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SegmentCreate {
  name: string
  description?: string | null
  definition: SegmentDef
}

export interface SegmentUpdate {
  name?: string
  description?: string | null
  definition?: SegmentDef
}

export interface ValidateResponse {
  valid: boolean
  errors?: string[]
  errors_by_metric?: Record<string, string[]>
}

// ── Attributes ───────────────────────────────────────────────────────────

export interface AttributeDefinition {
  key: string
  label: string
  type: 'string' | 'number' | 'boolean' | 'timestamp'
  source: string
  description: string | null
  created_at: string | null
  updated_at: string | null
}

// ── Fields (discovery) ───────────────────────────────────────────────────

export interface FieldSpec {
  key: string
  label: string
  type?: string
}

export interface FieldsResponse {
  dimensions: FieldSpec[]
  time_dimensions: FieldSpec[]
  attributes: FieldSpec[]
}

// ── Clients ──────────────────────────────────────────────────────────────

export const fetchSegments = () => get<Segment[]>('/api/segments')
export const fetchSegment = (id: string) => get<Segment>(`/api/segments/${id}`)
export const createSegment = (body: SegmentCreate) => post<Segment>('/api/segments', body)
export const updateSegment = (id: string, body: SegmentUpdate) =>
  put<{ status: string }>(`/api/segments/${id}`, body)
export const deleteSegment = (id: string) => del<{ status: string }>(`/api/segments/${id}`)
export const validateSegment = (body: { definition: SegmentDef; metric?: string }) =>
  post<ValidateResponse>('/api/segments/validate', body)

export const fetchAttributes = () => get<AttributeDefinition[]>('/api/attributes')
export const fetchAttributeValues = (key: string, limit = 100) =>
  get<{ key: string; values: unknown[] }>(`/api/attributes/${encodeURIComponent(key)}/values?limit=${limit}`)

export const fetchFields = (metric: string) =>
  get<FieldsResponse>(`/api/metrics/${metric}/fields`)
