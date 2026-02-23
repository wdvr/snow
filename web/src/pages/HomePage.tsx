import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Search, Trophy, ArrowRight, Loader2 } from 'lucide-react'
import { useResorts, useRegions, useSnowQualityBatch, useBestConditions } from '../hooks/useResorts'
import { ResortCard } from '../components/resort/ResortCard'
import { RegionFilter } from '../components/resort/RegionFilter'
import { QualityBadge } from '../components/resort/QualityBadge'
import { countryFlag } from '../utils/format'

type SortOption = 'quality' | 'snow' | 'name'

export function HomePage() {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<SortOption>('quality')

  const { data: regions, isLoading: regionsLoading } = useRegions()
  const { data: resorts, isLoading: resortsLoading } = useResorts(selectedRegion || undefined)
  const { data: bestConditions } = useBestConditions(5)

  // Fetch quality for all resorts
  const resortIds = useMemo(() => resorts?.map((r) => r.resort_id) ?? [], [resorts])
  const { data: qualityMap } = useSnowQualityBatch(resortIds)

  // Filter and sort resorts
  const filteredResorts = useMemo(() => {
    if (!resorts) return []
    let filtered = resorts

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
  }, [resorts, search, sortBy, qualityMap])

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
          {regions && (
            <RegionFilter
              regions={regions}
              selected={selectedRegion}
              onChange={setSelectedRegion}
            />
          )}

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
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
