import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createAttribute,
  getAttributeValues,
  importAttributesCsv,
  listAttributes,
  listCustomerAttributeRows,
  updateAttribute,
  type AttributeCreate,
  type AttributeUpdate,
  type CustomerAttributeRowsQuery,
} from '@/api/attributes'
import { fetchAttributes, fetchAttributeValues } from '@/api/segments'

export function useAttributes() {
  return useQuery({
    queryKey: ['attributes'],
    queryFn: listAttributes,
    staleTime: 60_000,
  })
}

export function useAttributeValues(key: string | null, limit = 100) {
  return useQuery({
    queryKey: ['attribute-values', key, limit],
    queryFn: () => getAttributeValues(key as string, limit),
    enabled: key != null && key.length > 0,
    staleTime: 30_000,
  })
}

export function useCustomerAttributeRows(query: CustomerAttributeRowsQuery) {
  return useQuery({
    queryKey: ['customer-attributes', query],
    queryFn: () => listCustomerAttributeRows(query),
    staleTime: 30_000,
  })
}

export function useCreateAttribute() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: AttributeCreate) => createAttribute(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['attributes'] }),
  })
}

export function useUpdateAttribute() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, body }: { key: string; body: AttributeUpdate }) =>
      updateAttribute(key, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['attributes'] }),
  })
}

export function useImportAttributesCsv() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      file,
      id_column,
      id_kind,
    }: {
      file: File
      id_column?: string
      id_kind?: 'id' | 'external' | 'email'
    }) => importAttributesCsv(file, { id_column, id_kind }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['attributes'] })
      qc.invalidateQueries({ queryKey: ['attribute-values'] })
      qc.invalidateQueries({ queryKey: ['customer-attributes'] })
    },
  })
}

// Re-exports preserved for callers that imported from the segments module.
export { fetchAttributes, fetchAttributeValues }
