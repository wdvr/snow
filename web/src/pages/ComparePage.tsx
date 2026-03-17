import { useState, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { X, Plus, Search, Loader2, ArrowLeft, Snowflake, Thermometer, Mountain, ArrowDown } from 'lucide-react'
import { useResorts, flattenResorts, useSnowQualityBatch } from '../hooks/useResorts'
import { QualityBadge } from '../components/resort/QualityBadge'
import { ResortLogo } from '../components/resort/ResortLogo'
import { countryFlag } from '../utils/format'
import { useUnits } from '../hooks/useUnits'
import { getQualityColor } from '../utils/colors'
import type { Resort, SnowQualitySummary } from '../api/types'

const MAX_COMPARE = 4

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [showSearch, setShowSearch] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const { formatTemp, formatSnow, formatSnowInt } = useUnits()

  // Get selected resort IDs from URL
  const selectedIds = useMemo(() => {
    const ids = searchParams.get('resorts')
    return ids ? ids.split(',').filter(Boolean) : []
  }, [searchParams])

  // Load all resorts for search
  const { data: resortsData, isLoading: resortsLoading } = useResorts()
  const allResorts = useMemo(() => flattenResorts(resortsData), [resortsData])

  // Batch quality for selected resorts
  const { data: qualityMap, isLoading: qualityLoading } = useSnowQualityBatch(selectedIds)

  // Filter resorts for search
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return []
    const lower = searchQuery.toLowerCase()
    return allResorts
      .filter(
        (r) =>
          !selectedIds.includes(r.resort_id) &&
          (r.name.toLowerCase().includes(lower) ||
            r.country.toLowerCase().includes(lower) ||
            r.region.toLowerCase().includes(lower)),
      )
      .slice(0, 8)
  }, [allResorts, searchQuery, selectedIds])

  // Get selected resort objects
  const selectedResorts = useMemo(() => {
    return selectedIds
      .map((id) => allResorts.find((r) => r.resort_id === id))
      .filter(Boolean) as Resort[]
  }, [selectedIds, allResorts])

  const addResort = (resortId: string) => {
    if (selectedIds.length >= MAX_COMPARE) return
    const next = [...selectedIds, resortId]
    setSearchParams({ resorts: next.join(',') })
    setSearchQuery('')
    setShowSearch(false)
  }

  const removeResort = (resortId: string) => {
    const next = selectedIds.filter((id) => id !== resortId)
    if (next.length === 0) {
      setSearchParams({})
    } else {
      setSearchParams({ resorts: next.join(',') })
    }
  }

  const isLoading = resortsLoading || qualityLoading

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        All Resorts
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Compare Resorts</h1>
          <p className="text-sm text-gray-500 mt-1">
            {selectedResorts.length === 0
              ? 'Add resorts to compare side by side'
              : `Comparing ${selectedResorts.length} resort${selectedResorts.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        {selectedIds.length < MAX_COMPARE && (
          <button
            onClick={() => setShowSearch(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Resort
          </button>
        )}
      </div>

      {/* Search modal */}
      {showSearch && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/30 backdrop-blur-sm" onClick={() => setShowSearch(false)}>
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="p-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search resorts..."
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  autoFocus
                />
              </div>
            </div>
            {searchResults.length > 0 && (
              <div className="border-t border-gray-100 max-h-64 overflow-y-auto">
                {searchResults.map((resort) => (
                  <button
                    key={resort.resort_id}
                    onClick={() => addResort(resort.resort_id)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left"
                  >
                    <ResortLogo name={resort.name} officialWebsite={resort.official_website} logoUrl={resort.logo_url} size={28} className="shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {countryFlag(resort.country)} {resort.name}
                      </p>
                      <p className="text-xs text-gray-500">{resort.region}</p>
                    </div>
                    <Plus className="w-4 h-4 text-blue-500 shrink-0" />
                  </button>
                ))}
              </div>
            )}
            {searchQuery && searchResults.length === 0 && (
              <div className="border-t border-gray-100 px-4 py-6 text-center text-sm text-gray-500">
                No resorts found
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {selectedResorts.length === 0 && !isLoading && (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-100 shadow-sm">
          <Mountain className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">No resorts selected</h2>
          <p className="text-sm text-gray-500 mb-4">
            Add up to {MAX_COMPARE} resorts to compare their conditions side by side.
          </p>
          <button
            onClick={() => setShowSearch(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Resort
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && selectedIds.length > 0 && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
      )}

      {/* Comparison grid */}
      {selectedResorts.length > 0 && !isLoading && (
        <div className="overflow-x-auto -mx-4 px-4">
          <div className={`grid gap-4 min-w-[${selectedResorts.length * 200}px]`}
            style={{ gridTemplateColumns: `repeat(${selectedResorts.length}, minmax(180px, 1fr))` }}>
            {/* Resort headers */}
            {selectedResorts.map((resort) => {
              const q = qualityMap?.[resort.resort_id]
              return (
                <div key={resort.resort_id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                  <div className="flex items-start justify-between mb-3">
                    <ResortLogo name={resort.name} officialWebsite={resort.official_website} logoUrl={resort.logo_url} size={36} className="shrink-0" />
                    <button
                      onClick={() => removeResort(resort.resort_id)}
                      className="p-1 rounded-full hover:bg-gray-100 transition-colors"
                    >
                      <X className="w-4 h-4 text-gray-400" />
                    </button>
                  </div>
                  <Link to={`/resort/${resort.resort_id}`} className="hover:text-blue-600 transition-colors">
                    <h3 className="font-semibold text-gray-900 text-sm mb-1">
                      {countryFlag(resort.country)} {resort.name}
                    </h3>
                  </Link>
                  <div className="mt-2">
                    <QualityBadge quality={q?.overall_quality} score={q?.snow_score} size="md" />
                  </div>
                </div>
              )
            })}

            {/* Stats rows */}
            {renderStatRow(selectedResorts, qualityMap, 'Fresh Snow', (q) => (
              <div className="flex items-center gap-1.5">
                <Snowflake className="w-4 h-4 text-blue-400" />
                <span className="font-semibold">{q?.snowfall_fresh_cm != null ? formatSnow(q.snowfall_fresh_cm) : '--'}</span>
              </div>
            ))}

            {renderStatRow(selectedResorts, qualityMap, '24h Snowfall', (q) => (
              <div className="flex items-center gap-1.5">
                <ArrowDown className="w-4 h-4 text-blue-300" />
                <span className="font-semibold">{q?.snowfall_24h_cm != null ? formatSnow(q.snowfall_24h_cm) : '--'}</span>
              </div>
            ))}

            {renderStatRow(selectedResorts, qualityMap, 'Temperature', (q) => (
              <div className="flex items-center gap-1.5">
                <Thermometer className="w-4 h-4 text-orange-400" />
                <span className="font-semibold">{q?.temperature_c != null ? formatTemp(q.temperature_c) : '--'}</span>
              </div>
            ))}

            {renderStatRow(selectedResorts, qualityMap, 'Snow Depth', (q) => (
              <div className="flex items-center gap-1.5">
                <Mountain className="w-4 h-4 text-gray-400" />
                <span className="font-semibold">{q?.snow_depth_cm != null ? formatSnowInt(q.snow_depth_cm) : '--'}</span>
              </div>
            ))}

            {renderStatRow(selectedResorts, qualityMap, '48h Forecast', (q) => (
              <div className="flex items-center gap-1.5">
                <Snowflake className="w-4 h-4 text-indigo-400" />
                <span className="font-semibold">{q?.predicted_snow_48h_cm != null ? formatSnow(q.predicted_snow_48h_cm) : '--'}</span>
              </div>
            ))}

            {renderStatRow(selectedResorts, qualityMap, 'Quality', (q) => {
              const color = getQualityColor(q?.overall_quality)
              return (
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color.hex }} />
                  <span className="text-sm capitalize">{q?.overall_quality?.replace(/_/g, ' ') ?? 'Unknown'}</span>
                </div>
              )
            })}

            {/* Elevation info */}
            {selectedResorts.map((resort) => (
              <div key={`elev-${resort.resort_id}`} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Elevation</p>
                <div className="space-y-1 text-sm text-gray-700">
                  {[...resort.elevation_points]
                    .sort((a, b) => b.elevation_meters - a.elevation_meters)
                    .map((ep) => (
                      <div key={ep.level} className="flex justify-between">
                        <span className="capitalize text-gray-500">{ep.level}</span>
                        <span className="font-medium">{ep.elevation_meters}m</span>
                      </div>
                    ))}
                </div>
              </div>
            ))}

            {/* Trail distribution */}
            {selectedResorts.map((resort) => (
              <div key={`trails-${resort.resort_id}`} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Trails</p>
                {resort.green_runs_pct != null || resort.blue_runs_pct != null ? (
                  <div className="space-y-1.5">
                    {resort.green_runs_pct != null && (
                      <TrailBar label="Green" pct={resort.green_runs_pct} color="bg-green-500" />
                    )}
                    {resort.blue_runs_pct != null && (
                      <TrailBar label="Blue" pct={resort.blue_runs_pct} color="bg-blue-500" />
                    )}
                    {resort.black_runs_pct != null && (
                      <TrailBar label="Black" pct={resort.black_runs_pct} color="bg-gray-900" />
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400">No data</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function renderStatRow(
  resorts: Resort[],
  qualityMap: Record<string, SnowQualitySummary> | undefined,
  label: string,
  renderValue: (q: SnowQualitySummary | undefined) => React.ReactNode,
) {
  return resorts.map((resort) => (
    <div key={`${label}-${resort.resort_id}`} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">{label}</p>
      {renderValue(qualityMap?.[resort.resort_id])}
    </div>
  ))
}

function TrailBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-10">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-700 w-8 text-right">{pct}%</span>
    </div>
  )
}
