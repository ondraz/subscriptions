import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  createSegment,
  deleteSegment,
  fetchSegments,
  fetchSegment,
  updateSegment,
  validateSegment,
  type SegmentCreate,
  type SegmentUpdate,
  type SegmentDef,
} from '@/api/segments'

const STALE = 60_000

// All segments. Workspace-shared — no user filter on the server.
export function useSegments() {
  return useQuery({ queryKey: ['segments'], queryFn: fetchSegments, staleTime: STALE })
}

export function useSegment(id: string | null) {
  return useQuery({
    queryKey: ['segment', id],
    queryFn: () => fetchSegment(id as string),
    enabled: id != null,
    staleTime: STALE,
  })
}

export function useCreateSegment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SegmentCreate) => createSegment(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['segments'] }),
  })
}

export function useUpdateSegment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: SegmentUpdate }) => updateSegment(id, body),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['segments'] })
      qc.invalidateQueries({ queryKey: ['segment', vars.id] })
    },
  })
}

export function useDeleteSegment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteSegment(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['segments'] }),
  })
}

export function useValidateSegment() {
  return useMutation({
    mutationFn: (body: { definition: SegmentDef; metric?: string }) => validateSegment(body),
  })
}
