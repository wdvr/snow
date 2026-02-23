import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Search, Trophy, ArrowRight, Loader2, MapPin, Navigation, Heart } from 'lucide-react'
import {
  useResorts,
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

type SortOption = 'quality' | 'snow' | 'name' | 'favorites'

export function HomePage() {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<SortOption>('quality')

  const geo = useGeolocation()
  const { favorites, toggleFavorite, isFavorite } = useFavorites()
  const { data: nearbyResorts } = useNearbyResorts(geo.latitude, geo.longitude)

  const { data: regions, isLoading: regionsLoading } = useRegions()
  const { data: resorts, isLoading: resortsLoading } = useResorts(
    selectedRegion === 'favorites' ? undefined : selectedRegion || undefined,
  )
  const { data: bestConditions } = useBestConditions(5)

  // Fetch quality for all resorts
  const resortIds = useMemo(() => resorts?.map((r) => r.resort_id) ?? [], [resorts])
  const { data: qualityMap } = useSnowQualityBatch(resortIds)

  // Filter and sort resorts
  const filteredResorts = useMemo(() => {
    if (!resorts) return []
    let filtered = resorts

    // Favorites filter
    if (selectedRegion === 'favorites') {
      filtered = filtered.filter((r) => favorites.includes(r.resort_id))
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

    // Sort
    return [...filtered].sort((a, b) => {
      const qa = qualityMap?.[a.resort_id]
      const qb = qualityMap?.[b.resort_id]

      // Favorites first sort: put favorites at top, then sort by quality
      if (sortBy === 'favorites') {
        const aFav = favorites.includes(a.resort_id) ? 1 : 0
        const bFav = favorites.includes(b.resort_id) ? 1 : 0
        if (aFav !== bFav) return bFav - aFav
        const scoreA = qa?.snow_score ?? -1
        const scoreB = qb?.snow_score ?? -1
        return scoreB - scoreA
      }

      switch (sortBy) {
        case 'quality': {
          const scoreA = qa?.snow_score ?? -1
          const scoreB = qb?.snow_score ?? -1
          return scoreB - scoreA
        }
        case 'snow': {
          const snowA = qa?.snowfall_fresh_cm ?? 0
          const snowB = qb?.snowfall_fresh_cm ?? 0
          return snowB - snowA
        }
        case 'name':
          return a.name.localeCompare(b.name)
        default:
          return 0
      }
    })
  }, [resorts, search, sortBy, qualityMap, selectedRegion, favorites])

  const isLoading = resortsLoading || regionsLoading

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

        {/* Region filter + sort */}
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

          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {isLoading ? 'Loading...' : `${filteredResorts.length} resorts`}
            </p>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="quality">Quality Score</option>
                <option value="snow">Fresh Snow</option>
                <option value="name">Name</option>
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredResorts.map((resort) => (
              <ResortCard
                key={resort.resort_id}
                resort={resort}
                quality={qualityMap?.[resort.resort_id]}
                isFavorite={isFavorite(resort.resort_id)}
                onToggleFavorite={toggleFavorite}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
