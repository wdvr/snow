import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Region, SnowQualitySummary } from '../api/types'

export function useResorts(region?: string) {
  return useQuery({
    queryKey: ['resorts', region],
    queryFn: () => api.getResorts(region ? { region } : undefined),
    staleTime: 5 * 60 * 1000,
  })
}

export function useResort(id: string) {
  return useQuery({
    queryKey: ['resort', id],
    queryFn: () => api.getResort(id),
    staleTime: 5 * 60 * 1000,
    enabled: !!id,
  })
}

export function useRegions() {
  return useQuery({
    queryKey: ['regions'],
    queryFn: () => api.getRegions(),
    staleTime: 10 * 60 * 1000,
  })
}

export function useSnowQualityBatch(resortIds: string[]) {
  return useQuery({
    queryKey: ['snow-quality-batch', [...resortIds].sort().join(',')],
    queryFn: () => api.getSnowQualityBatch(resortIds),
    staleTime: 5 * 60 * 1000,
    enabled: resortIds.length > 0,
    select: (data): Record<string, SnowQualitySummary> => {
      // The API may return an object keyed by resort_id, or an array
      if (Array.isArray(data)) {
        const map: Record<string, SnowQualitySummary> = {}
        for (const item of data as unknown as SnowQualitySummary[]) {
          map[item.resort_id] = item
        }
        return map
      }
      return data
    },
  })
}

export function useBestConditions(limit = 5) {
  return useQuery({
    queryKey: ['best-conditions', limit],
    queryFn: () => api.getBestConditions(limit),
    staleTime: 5 * 60 * 1000,
  })
}

export function useNearbyResorts(lat: number | null, lon: number | null, radius = 300) {
  return useQuery({
    queryKey: ['nearby-resorts', lat, lon, radius],
    queryFn: () => api.getNearbyResorts(lat!, lon!, radius, 10),
    staleTime: 10 * 60 * 1000,
    enabled: lat !== null && lon !== null,
  })
}

export function useResortsByRegion(_regions: Region[] | undefined, selectedRegion: string | null) {
  // This hook is for convenience - actual filtering is handled by the API
  return useResorts(selectedRegion || undefined)
}
