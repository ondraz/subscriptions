import { del, get, post, postForm, put } from './client'
import type { AttributeDefinition } from './segments'

export type { AttributeDefinition }

export type AttributeType = 'string' | 'number' | 'boolean' | 'timestamp'

export interface AttributeCreate {
  key: string
  label?: string | null
  type: AttributeType
  description?: string | null
}

export interface AttributeUpdate {
  label?: string | null
  description?: string | null
}

export interface AttributeValuesResponse {
  key: string
  values: unknown[]
}

export interface CustomerAttributesSetBody {
  attributes: Record<string, unknown>
}

export interface CsvImportSummary {
  rows_read: number
  rows_upserted: number
  unknown_customers: string[]
  keys_created: string[]
}

export interface CustomerAttributeRow {
  customer_id: string
  customer_external_id: string | null
  customer_name: string | null
  customer_email: string | null
  key: string
  value: string | number | boolean | null
  origin: string
  updated_at: string | null
}

export interface CustomerAttributeRowsResponse {
  total: number
  rows: CustomerAttributeRow[]
  limit: number
  offset: number
}

export const listAttributes = () => get<AttributeDefinition[]>('/api/attributes')

export const createAttribute = (body: AttributeCreate) =>
  post<AttributeDefinition>('/api/attributes', body)

export const updateAttribute = (key: string, body: AttributeUpdate) =>
  put<{ status: string }>(`/api/attributes/${encodeURIComponent(key)}`, body)

export const getAttributeValues = (key: string, limit = 100) =>
  get<AttributeValuesResponse>(
    `/api/attributes/${encodeURIComponent(key)}/values?limit=${limit}`,
  )

export const setCustomerAttributes = (customerId: string, body: CustomerAttributesSetBody) =>
  post<{ upserted: number }>(
    `/api/customers/${encodeURIComponent(customerId)}/attributes`,
    body,
  )

export const deleteCustomerAttribute = (customerId: string, key: string) =>
  del<{ status: string }>(
    `/api/customers/${encodeURIComponent(customerId)}/attributes/${encodeURIComponent(key)}`,
  )

export interface CustomerAttributeRowsQuery {
  key?: string | null
  search?: string | null
  limit?: number
  offset?: number
}

export const listCustomerAttributeRows = (q: CustomerAttributeRowsQuery = {}) => {
  const params = new URLSearchParams()
  if (q.key) params.set('key', q.key)
  if (q.search) params.set('search', q.search)
  if (q.limit != null) params.set('limit', String(q.limit))
  if (q.offset != null) params.set('offset', String(q.offset))
  const qs = params.toString()
  return get<CustomerAttributeRowsResponse>(
    `/api/customer-attributes${qs ? `?${qs}` : ''}`,
  )
}

export const importAttributesCsv = (
  file: File,
  opts: { id_column?: string; id_kind?: 'id' | 'external' | 'email' } = {},
) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('id_column', opts.id_column ?? 'customer_id')
  fd.append('id_kind', opts.id_kind ?? 'id')
  return postForm<CsvImportSummary>('/api/attributes/import', fd)
}
