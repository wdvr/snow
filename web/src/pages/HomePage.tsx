import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Search, Trophy, ArrowRight, Loader2, MapPin, Navigation, Heart, ChevronDown } from 'lucide-react'
import {
  useResorts,
  flattenResorts,
  getTotalCount,
  useRegions,
  useSnowQualityBatch,
  useBestConditions,
  useNearbyResorts,
} from '../hooks/useResorts'
import { useGeolocation } from '../hooks/useGeolocation'
import { useFavorites } from '../hooks/useFavorites'
import { ResortCard } from '../components/resort/ResortCard'
import { RegionFilter } from '../components/resort/RegionFilter'
import { QualityBadge } from '../components/resort/QualityBadge'
import { countryFlag } from '../utils/format'

type SortOption = 'quality' | 'snow' | 'name' | 'favorites' | 'distance'
type PassFilter = 'all' | 'epic' | 'ikon'

/** Map client-side sort option to API sort_by param */
function toApiSort(sortBy: SortOption): { sort_by?: string; sort_order?: string } {
  switch (sortBy) {
    case 'quality':
      return { sort_by: 'quality_score', sort_order: 'desc' }
    case 'snow':
      return { sort_by: 'snowfall', sort_order: 'desc' }
    case 'name':
      return { sort_by: 'name', sort_order: 'asc' }
    default:
      // 'favorites' and 'distance' are client-side sorts — fall back to quality
      return { sort_by: 'quality_score', sort_order: 'desc' }
  }
}

/** Haversine distance in km between two lat/lon pairs */
function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function HomePage() {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<SortOption>('quality')
  const [passFilter, setPassFilter] = useState<PassFilter>('all')

  const geo = useGeolocation()
  const { favorites, toggleFavorite, isFavorite } = useFavorites()
  const { data: nearbyResorts } = useNearbyResorts(geo.latitude, geo.longitude)

  const { data: regions, isLoading: regionsLoading } = useRegions()

  // Compute API sort params from the selected sort option
  const apiSort = toApiSort(sortBy)

  const {
    data: resortsData,
    isLoading: resortsLoading,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useResorts({
    region: selectedRegion === 'favorites' ? undefined : selectedRegion || undefined,
    sortBy: apiSort.sort_by,
    sortOrder: apiSort.sort_order,
  })

  const resorts = flattenResorts(resortsData)
  const totalCount = getTotalCount(resortsData)

  const { data: bestConditions } = useBestConditions(5)

  // Fetch quality for loaded resorts
  const resortIds = useMemo(() => resorts.map((r) => r.resort_id), [resorts])
  const { data: qualityMap } = useSnowQualityBatch(resortIds)

  // Compute distances for each resort (for distance sorting)
  const distanceMap = useMemo(() => {
    if (resorts.length === 0 || geo.latitude == null || geo.longitude == null) return null
    const map: Record<string, number> = {}
    for (const r of resorts) {
      // Use the first elevation point's lat/lon (usually mid or base)
      const ep = r.elevation_points[0]
      if (ep) {
        map[r.resort_id] = haversineKm(geo.latitude, geo.longitude, ep.latitude, ep.longitude)
      }
    }
    return map
  }, [resorts, geo.latitude, geo.longitude])

  // Filter and sort resorts (client-side filtering for search, favorites, pass; client-side sort for distance/favorites)
  const filteredResorts = useMemo(() => {
    if (resorts.length === 0) return []
    let filtered = resorts

    // Favorites filter
    if (selectedRegion === 'favorites') {
      filtered = filtered.filter((r) => favorites.includes(r.resort_id))
    }

    // Pass filter
    if (passFilter === 'epic') {
      filtered = filtered.filter((r) => r.epic_pass != null)
    } else if (passFilter === 'ikon') {
      filtered = filtered.filter((r) => r.ikon_pass != null)
    }

    // Search filter
    if (search) {
      const lower = search.toLowerCase()
      filtered = filtered.filter(
        (r) =>
          r.name.toLowerCase().includes(lower) ||
          r.region.toLowerCase().includes(lower) ||
          r.country.toLowerCase().includes(lower),
      )
    }

    // Client-side sort for favorites-first and distance modes
    // (quality, snow, name are handled server-side)
    if (sortBy === 'favorites') {
      return [...filtered].sort((a, b) => {
        const aFav = favorites.includes(a.resort_id) ? 1 : 0
        const bFav = favorites.includes(b.resort_id) ? 1 : 0
        if (aFav !== bFav) return bFav - aFav
        const qa = qualityMap?.[a.resort_id]
        const qb = qualityMap?.[b.resort_id]
        const scoreA = qa?.snow_score ?? -1
        const scoreB = qb?.snow_score ?? -1
        return scoreB - scoreA
      })
    }

    if (sortBy === 'distance') {
      return [...filtered].sort((a, b) => {
        const distA = distanceMap?.[a.resort_id] ?? Infinity
        const distB = distanceMap?.[b.resort_id] ?? Infinity
        return distA - distB
      })
    }

    // Server already sorted for quality/snow/name — preserve order
    return filtered
  }, [resorts, search, sortBy, qualityMap, selectedRegion, favorites, passFilter, distanceMap])

  const isLoading = resortsLoading || regionsLoading

  // Count text: "Showing X of Y resorts"
  const countText = (() => {
    if (isLoading) return 'Loading...'
    if (search || passFilter !== 'all' || selectedRegion === 'favorites') {
      // Client-side filtering active — show filtered count
      return `${filteredResorts.length} resorts`
    }
    if (totalCount > 0 && resorts.length < totalCount) {
      return `Showing ${resorts.length} of ${totalCount} resorts`
    }
    return `${filteredResorts.length} resorts`
  })()

  return (
    <div>
      {/* Hero */}
      <section className="bg-gradient-to-br from-blue-600 via-blue-700 to-slate-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-3">
            Find the best powder conditions
          </h1>
          <p className="text-blue-100 text-lg mb-8 max-w-2xl">
            Real-time snow quality tracking across 130+ ski resorts worldwide.
            AI-powered analysis to find your next powder day.
          </p>
          <div className="relative max-w-xl">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search resorts..."
              className="w-full pl-12 pr-4 py-3.5 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white placeholder-blue-200 focus:outline-none focus:ring-2 focus:ring-white/30 focus:bg-white/15 transition-all"
            />
          </div>
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Near You */}
        {!geo.requested ? (
          <section className="mb-10">
            <button
              onClick={geo.requestLocation}
              className="w-full flex items-center justify-between bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100 p-4 hover:from-blue-100 hover:to-indigo-100 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="bg-blue-100 rounded-lg p-2 group-hover:bg-blue-200 transition-colors">
                  <Navigation className="w-5 h-5 text-blue-600" />
                </div>
                <div className="text-left">
                  <p className="font-medium text-gray-900">Find resorts near you</p>
                  <p className="text-sm text-gray-500">
                    Enable location to see nearby conditions
                  </p>
                </div>
              </div>
              <MapPin className="w-5 h-5 text-blue-400" />
            </button>
          </section>
        ) : geo.latitude &&
          nearbyResorts?.resorts &&
          nearbyResorts.resorts.length > 0 &&
          !search &&
          !selectedRegion ? (
          <section className="mb-10">
            <div className="flex items-center gap-2 mb-4">
              <MapPin className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold text-gray-900">Near You</h2>
            </div>
            <div className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 snap-x">
              {nearbyResorts.resorts.slice(0, 8).map(({ resort, distance_km }) => (
                <Link
                  key={resort.resort_id}
                  to={`/resort/${resort.resort_id}`}
                  className="flex-shrink-0 w-52 bg-white rounded-xl shadow-sm border border-gray-100 p-3 hover:shadow-md transition-shadow snap-start"
                >
                  <p className="font-medium text-gray-900 text-sm truncate">{resort.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {countryFlag(resort.country)} {Math.round(distance_km)} km away
                  </p>
                  <div className="mt-2">
                    <QualityBadge
                      quality={qualityMap?.[resort.resort_id]?.overall_quality}
                      score={qualityMap?.[resort.resort_id]?.snow_score}
                      size="sm"
                    />
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ) : null}

        {/* Best Conditions */}
        {bestConditions && bestConditions.length > 0 && !search && !selectedRegion && (
          <section className="mb-10">
            <div className="flex items-center gap-2 mb-4">
              <Trophy className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-semibold text-gray-900">Best Conditions Right Now</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {bestConditions.map((rec, i) => (
                <Link
                  key={rec.resort.resort_id}
                  to={`/resort/${rec.resort.resort_id}`}
                  className="flex items-center gap-3 bg-white rounded-xl shadow-sm border border-gray-100 p-3 hover:shadow-md transition-shadow group"
                >
                  <span className="text-lg font-bold text-gray-300 w-6 text-center">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-900 text-sm truncate group-hover:text-blue-600 transition-colors">
                      {countryFlag(rec.resort.country)} {rec.resort.name}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <QualityBadge
                        quality={rec.snow_quality}
                        score={rec.snow_score}
                        size="sm"
                      />
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-300 shrink-0" />
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Region filter + pass filter + sort */}
        <section className="mb-6 space-y-4">
          <div className="flex items-center gap-2">
            {favorites.length > 0 && (
              <button
                onClick={() =>
                  setSelectedRegion(selectedRegion === 'favorites' ? null : 'favorites')
                }
                className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors shrink-0 ${
                  selectedRegion === 'favorites'
                    ? 'bg-red-500 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                <Heart
                  className={`w-3.5 h-3.5 ${selectedRegion === 'favorites' ? 'fill-white' : 'fill-red-500 text-red-500'}`}
                />
                Favorites
                <span className="text-xs opacity-70">{favorites.length}</span>
              </button>
            )}
            <div className="min-w-0 flex-1">
              {regions && (
                <RegionFilter
                  regions={regions}
                  selected={selectedRegion === 'favorites' ? null : selectedRegion}
                  onChange={(region) => setSelectedRegion(region)}
                />
              )}
            </div>
          </div>

          {/* Pass filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500 shrink-0">Pass:</span>
            {([
              { value: 'all' as PassFilter, label: 'All', colors: 'bg-blue-600 text-white' },
              { value: 'epic' as PassFilter, label: 'Epic Pass', colors: 'bg-purple-600 text-white' },
              { value: 'ikon' as PassFilter, label: 'Ikon Pass', colors: 'bg-orange-500 text-white' },
            ]).map(({ value, label, colors }) => (
              <button
                key={value}
                onClick={() => setPassFilter(value)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                  passFilter === value
                    ? colors
                    : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {countText}
            </p>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => {
                  const val = e.target.value as SortOption
                  if (val === 'distance' && geo.latitude == null) {
                    geo.requestLocation()
                  }
                  setSortBy(val)
                }}
                className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="quality">Quality Score</option>
                <option value="snow">Fresh Snow</option>
                <option value="name">Name</option>
                <option value="distance">Distance</option>
                {favorites.length > 0 && <option value="favorites">Favorites First</option>}
              </select>
            </div>
          </div>
        </section>

        {/* Resort grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          </div>
        ) : filteredResorts.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500">No resorts found</p>
            {search && (
              <button
                onClick={() => setSearch('')}
                className="mt-2 text-blue-600 text-sm hover:underline"
              >
                Clear search
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredResorts.map((resort) => (
                <ResortCard
                  key={resort.resort_id}
                  resort={resort}
                  quality={qualityMap?.[resort.resort_id]}
                  isFavorite={isFavorite(resort.resort_id)}
                  onToggleFavorite={toggleFavorite}
                  distanceKm={sortBy === 'distance' ? (distanceMap?.[resort.resort_id] ?? null) : null}
                />
              ))}
            </div>

            {/* Load more button */}
            {hasNextPage && (
              <div className="flex justify-center mt-8">
                <button
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className="flex items-center gap-2 px-6 py-3 bg-white border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isFetchingNextPage ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Loading more...
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-4 h-4" />
                      Load more resorts
                    </>
                  )}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
