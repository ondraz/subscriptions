import { useQuery } from '@tanstack/react-query'
import { fetchFields } from '@/api/segments'

// Discovery endpoint: returns dimensions, time_dimensions, and attributes
// for a given metric's primary cube.  Drives the segment builder's
// field-picker dropdowns and replaces the hardcoded *_DIMENSIONS lists.
export function useFields(metric: string) {
  return useQuery({
    queryKey: ['metric-fields', metric],
    queryFn: () => fetchFields(metric),
    staleTime: 5 * 60_000, // fields rarely change; cache longer
  })
}
