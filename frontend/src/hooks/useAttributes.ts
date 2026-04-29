import { useQuery } from '@tanstack/react-query'
import { fetchAttributes, fetchAttributeValues } from '@/api/segments'

export function useAttributes() {
  return useQuery({
    queryKey: ['attributes'],
    queryFn: fetchAttributes,
    staleTime: 60_000,
  })
}

export function useAttributeValues(key: string | null, limit = 100) {
  return useQuery({
    queryKey: ['attribute-values', key, limit],
    queryFn: () => fetchAttributeValues(key as string, limit),
    enabled: key != null && key.length > 0,
    staleTime: 30_000,
  })
}
