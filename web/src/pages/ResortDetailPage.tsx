import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  ExternalLink,
  Mountain,
  Loader2,
  Snowflake,
  Thermometer,
  Clock,
  AlertCircle,
  Heart,
} from 'lucide-react'
import { useResort } from '../hooks/useResorts'
import { useFavorites } from '../hooks/useFavorites'
import {
  useResortConditions,
  useResortTimeline,
  useResortHistory,
  useResortSnowQuality,
  useConditionReports,
} from '../hooks/useConditions'
import { QualityBadge } from '../components/resort/QualityBadge'
import { ConditionsTable } from '../components/resort/ConditionsTable'
import { ForecastChart, HistoryChart } from '../components/resort/ForecastChart'
import { TrailDistribution } from '../components/resort/TrailDistribution'
import { formatTemp, formatSnowCm, formatDate, countryFlag, regionDisplayName } from '../utils/format'
import type { SnowQuality, ConditionType } from '../api/types'

type Tab = 'conditions' | 'forecast' | 'history' | 'reports'

const CONDITION_TYPE_LABELS: Record<ConditionType, string> = {
  powder: 'Powder',
  packed_powder: 'Packed Powder',
  soft: 'Soft',
  ice: 'Ice',
  crud: 'Crud',
  spring: 'Spring',
  hardpack: 'Hardpack',
  windblown: 'Windblown',
}

export function ResortDetailPage() {
  const { resortId } = useParams<{ resortId: string }>()
  const [activeTab, setActiveTab] = useState<Tab>('conditions')

  const { toggleFavorite, isFavorite } = useFavorites()
  const { data: resort, isLoading: resortLoading } = useResort(resortId!)
  const { data: conditions, isLoading: conditionsLoading } = useResortConditions(resortId!)
  const { data: timeline } = useResortTimeline(resortId!)
  const { data: history } = useResortHistory(resortId!)
  const { data: snowQuality } = useResortSnowQuality(resortId!)
  const { data: reports } = useConditionReports(resortId!)

  if (resortLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    )
  }

  if (!resort) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Resort not found</h2>
        <Link to="/" className="text-blue-600 hover:underline text-sm">
          Back to all resorts
        </Link>
      </div>
    )
  }

  const qualityData = snowQuality as Record<string, unknown> | undefined
  const overallQuality = qualityData?.overall_quality as string | undefined
  const snowScore = qualityData?.snow_score as number | undefined
  const explanation = qualityData?.explanation as string | undefined

  const tabs: { id: Tab; label: string }[] = [
    { id: 'conditions', label: 'Conditions' },
    { id: 'forecast', label: 'Forecast' },
    { id: 'history', label: 'History' },
    { id: 'reports', label: 'Reports' },
  ]

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Back link */}
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        All Resorts
      </Link>

      {/* Resort header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
                {countryFlag(resort.country)} {resort.name}
              </h1>
              <button
                onClick={() => toggleFavorite(resortId!)}
                className="p-2 rounded-full hover:bg-gray-100 transition-colors"
              >
                <Heart
                  className={`w-6 h-6 ${isFavorite(resortId!) ? 'fill-red-500 text-red-500' : 'text-gray-300'}`}
                />
              </button>
            </div>
            <p className="text-gray-500">
              {regionDisplayName(resort.region)}, {resort.country}
              {resort.official_website && (
                <>
                  {' '}
                  <a
                    href={resort.official_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                  >
                    Website <ExternalLink className="w-3 h-3" />
                  </a>
                </>
              )}
              {resort.trail_map_url && (
                <>
                  {' '}
                  <a
                    href={resort.trail_map_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                  >
                    Trail Map <ExternalLink className="w-3 h-3" />
                  </a>
                </>
              )}
            </p>

            {/* Elevation info */}
            <div className="flex items-center gap-4 mt-3 text-sm text-gray-600">
              <div className="flex items-center gap-1.5">
                <Mountain className="w-4 h-4 text-gray-400" />
                {resort.elevation_points
                  .sort((a, b) => a.elevation_meters - b.elevation_meters)
                  .map((ep) => `${ep.elevation_meters}m`)
                  .join(' - ')}
              </div>
              {(resort.epic_pass || resort.ikon_pass) && (
                <div className="flex items-center gap-1.5">
                  {resort.epic_pass && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 font-medium">
                      Epic: {resort.epic_pass}
                    </span>
                  )}
                  {resort.ikon_pass && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 font-medium">
                      Ikon: {resort.ikon_pass}
                    </span>
                  )}
                </div>
              )}
            </div>
            {/* Trail distribution */}
            {(resort.green_runs_pct != null || resort.blue_runs_pct != null || resort.black_runs_pct != null) && (
              <TrailDistribution resort={resort} />
            )}
          </div>

          {/* Overall quality */}
          <div className="flex flex-col items-center sm:items-end gap-2">
            <QualityBadge
              quality={overallQuality as SnowQuality}
              score={snowScore}
              size="lg"
            />
            {explanation && (
              <p className="text-xs text-gray-500 max-w-xs text-center sm:text-right">
                {explanation}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {tab.label}
            {tab.id === 'reports' && reports && reports.length > 0 && (
              <span className="ml-1.5 text-xs opacity-70">{reports.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        {activeTab === 'conditions' && (
          <div>
            {conditionsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
              </div>
            ) : conditions ? (
              <ConditionsTable conditions={conditions} />
            ) : (
              <p className="text-center py-8 text-gray-500">
                No conditions data available
              </p>
            )}
          </div>
        )}

        {activeTab === 'forecast' && (
          <div>
            {timeline ? (
              <ForecastChart timeline={timeline.timeline} />
            ) : (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div>
            {history ? (
              <div>
                {/* Season summary */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                  <div className="bg-blue-50 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 text-xs text-blue-600 mb-1">
                      <Snowflake className="w-3.5 h-3.5" />
                      Season Total
                    </div>
                    <p className="text-lg font-bold text-gray-900">
                      {Math.round(history.season_summary.total_snowfall_cm)} cm
                    </p>
                    <p className="text-xs text-gray-500">
                      {Math.round(history.season_summary.total_snowfall_cm / 2.54)}"
                    </p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 text-xs text-blue-600 mb-1">
                      <Snowflake className="w-3.5 h-3.5" />
                      Best Day
                    </div>
                    {(() => {
                      const best = history.season_summary.best_day
                      return best ? (
                        <>
                          <p className="text-lg font-bold text-gray-900">
                            {formatSnowCm(best.snowfall_24h_cm)}
                          </p>
                          <p className="text-xs text-gray-500">{formatDate(best.date)}</p>
                        </>
                      ) : (
                        <p className="text-lg font-bold text-gray-900">--</p>
                      )
                    })()}
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 text-xs text-blue-600 mb-1">
                      <Thermometer className="w-3.5 h-3.5" />
                      Avg High
                    </div>
                    {(() => {
                      const temps = history.history
                        .filter((d) => d.temp_max_c != null)
                        .map((d) => d.temp_max_c!)
                      const avg = temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : null
                      return <p className="text-lg font-bold text-gray-900">{formatTemp(avg)}</p>
                    })()}
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 text-xs text-blue-600 mb-1">
                      <Clock className="w-3.5 h-3.5" />
                      Snow Days
                    </div>
                    <p className="text-lg font-bold text-gray-900">
                      {history.season_summary.snow_days}
                    </p>
                    <p className="text-xs text-gray-500">of {history.season_summary.days_tracked} days</p>
                  </div>
                </div>
                <HistoryChart history={history.history} />
              </div>
            ) : (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
              </div>
            )}
          </div>
        )}

        {activeTab === 'reports' && (
          <div>
            {reports && reports.length > 0 ? (
              <div className="space-y-3">
                {reports.map((report) => (
                  <div
                    key={report.report_id}
                    className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-gray-900">
                          {CONDITION_TYPE_LABELS[report.condition_type as ConditionType] ??
                            report.condition_type}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                          {report.score}/10
                        </span>
                        {report.elevation_level && (
                          <span className="text-xs text-gray-400">
                            {report.elevation_level}
                          </span>
                        )}
                      </div>
                      {report.comment && (
                        <p className="text-sm text-gray-600">{report.comment}</p>
                      )}
                      <p className="text-xs text-gray-400 mt-1">
                        {report.user_display_name ?? 'Anonymous'} &middot;{' '}
                        {formatDate(report.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center py-8 text-gray-500">
                No condition reports yet. Check back later!
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
