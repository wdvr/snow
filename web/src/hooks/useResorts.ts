import { useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Resort, Region, SnowQualitySummary } from '../api/types'

const PAGE_SIZE = 50

export interface UseResortsOptions {
  region?: string
  sortBy?: string
  sortOrder?: string
}

export function useResorts(options?: UseResortsOptions) {
  return useInfiniteQuery({
    queryKey: ['resorts', options?.region, options?.sortBy, options?.sortOrder],
    queryFn: async ({ pageParam = 0 }) => {
      return api.getResorts({
        region: options?.region,
        limit: PAGE_SIZE,
        offset: pageParam as number,
        sort_by: options?.sortBy,
        sort_order: options?.sortOrder,
      })
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((sum, page) => sum + page.resorts.length, 0)
      if (loaded >= lastPage.total_count) return undefined
      return loaded
    },
    staleTime: 5 * 60 * 1000,
  })
}

/** Flatten all pages into a single array of resorts */
export function flattenResorts(data: { pages: Array<{ resorts: Resort[]; total_count: number }> } | undefined): Resort[] {
  if (!data) return []
  return data.pages.flatMap((page) => page.resorts)
}

/** Get total count from paginated data */
export function getTotalCount(data: { pages: Array<{ resorts: Resort[]; total_count: number }> } | undefined): number {
  if (!data || data.pages.length === 0) return 0
  return data.pages[0].total_count
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
  return useResorts({ region: selectedRegion || undefined })
}
