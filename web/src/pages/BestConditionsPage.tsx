import { Link } from 'react-router-dom'
import { Trophy, Snowflake, Thermometer, ArrowRight, Loader2, MapPin, Navigation, TrendingUp } from 'lucide-react'
import { useBestConditions, useNearbyResorts } from '../hooks/useResorts'
import { useGeolocation } from '../hooks/useGeolocation'
import { QualityBadge } from '../components/resort/QualityBadge'
import { ResortLogo } from '../components/resort/ResortLogo'
import { countryFlag, regionDisplayName } from '../utils/format'
import { useUnits } from '../hooks/useUnits'

export function BestConditionsPage() {
  const { formatTemp, formatSnow } = useUnits()
  const geo = useGeolocation()
  const { data: bestConditions, isLoading: bestLoading } = useBestConditions(20)
  const { data: nearbyData, isLoading: nearbyLoading } = useNearbyResorts(
    geo.latitude,
    geo.longitude,
    500,
  )

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Trophy className="w-7 h-7 text-amber-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Best Conditions</h1>
          <p className="text-sm text-gray-500">Top resorts ranked by current snow quality</p>
        </div>
      </div>

      {/* Nearby Recommendations */}
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
                <p className="font-medium text-gray-900">Find best conditions near you</p>
                <p className="text-sm text-gray-500">
                  Enable location to see nearby recommendations
                </p>
              </div>
            </div>
            <MapPin className="w-5 h-5 text-blue-400" />
          </button>
        </section>
      ) : nearbyLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
        </div>
      ) : nearbyData?.resorts && nearbyData.resorts.length > 0 ? (
        <section className="mb-10">
          <div className="flex items-center gap-2 mb-4">
            <MapPin className="w-5 h-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-gray-900">Best Near You</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {nearbyData.resorts.slice(0, 6).map(({ resort, distance_km }) => (
              <Link
                key={resort.resort_id}
                to={`/resort/${resort.resort_id}`}
                className="flex items-center gap-3 bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow group"
              >
                <ResortLogo name={resort.name} officialWebsite={resort.official_website} logoUrl={resort.logo_url} size={36} className="shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-gray-900 text-sm truncate group-hover:text-blue-600 transition-colors">
                    {countryFlag(resort.country)} {resort.name}
                  </p>
                  <p className="text-xs text-gray-500">{Math.round(distance_km)} km away</p>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-300 shrink-0" />
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {/* Global Best Conditions */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-emerald-500" />
          <h2 className="text-lg font-semibold text-gray-900">Top 20 Worldwide</h2>
        </div>

        {bestLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          </div>
        ) : !bestConditions || bestConditions.length === 0 ? (
          <p className="text-center py-12 text-gray-500">No conditions data available</p>
        ) : (
          <div className="space-y-3">
            {bestConditions.map((rec, i) => (
              <Link
                key={rec.resort.resort_id}
                to={`/resort/${rec.resort.resort_id}`}
                className="flex items-center gap-4 bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow group"
              >
                <span className={`text-xl font-bold w-8 text-center shrink-0 ${
                  i === 0 ? 'text-amber-500' : i === 1 ? 'text-gray-400' : i === 2 ? 'text-amber-700' : 'text-gray-300'
                }`}>
                  {i + 1}
                </span>

                <ResortLogo name={rec.resort.name} officialWebsite={rec.resort.official_website} logoUrl={rec.resort.logo_url} size={40} className="shrink-0" />

                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                    {countryFlag(rec.resort.country)} {rec.resort.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {regionDisplayName(rec.resort.region)}
                  </p>
                  {rec.reason && (
                    <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{rec.reason}</p>
                  )}
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="hidden sm:flex flex-col items-end gap-1 text-xs text-gray-500">
                    <div className="flex items-center gap-1">
                      <Snowflake className="w-3 h-3 text-blue-400" />
                      <span>{formatSnow(rec.fresh_snow_cm)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Thermometer className="w-3 h-3 text-orange-400" />
                      <span>{formatTemp(rec.current_temp_celsius)}</span>
                    </div>
                  </div>
                  <QualityBadge quality={rec.snow_quality} score={rec.snow_score} size="md" />
                  <ArrowRight className="w-4 h-4 text-gray-300" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
