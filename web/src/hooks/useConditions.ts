import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useResortConditions(resortId: string) {
  return useQuery({
    queryKey: ['conditions', resortId],
    queryFn: () => api.getResortConditions(resortId),
    staleTime: 2 * 60 * 1000,
    enabled: !!resortId,
  })
}

export function useResortTimeline(resortId: string) {
  return useQuery({
    queryKey: ['timeline', resortId],
    queryFn: () => api.getResortTimeline(resortId),
    staleTime: 5 * 60 * 1000,
    enabled: !!resortId,
  })
}

export function useResortHistory(resortId: string, days = 30) {
  return useQuery({
    queryKey: ['history', resortId, days],
    queryFn: () => api.getResortHistory(resortId, days),
    staleTime: 10 * 60 * 1000,
    enabled: !!resortId,
  })
}

export function useResortSnowQuality(resortId: string) {
  return useQuery({
    queryKey: ['snow-quality', resortId],
    queryFn: () => api.getResortSnowQuality(resortId),
    staleTime: 5 * 60 * 1000,
    enabled: !!resortId,
  })
}

export function useConditionReports(resortId: string) {
  return useQuery({
    queryKey: ['condition-reports', resortId],
    queryFn: () => api.getConditionReports(resortId),
    staleTime: 2 * 60 * 1000,
    enabled: !!resortId,
  })
}
