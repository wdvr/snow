import { Link } from 'react-router-dom'
import { Thermometer, Snowflake, Wind, Heart, Navigation } from 'lucide-react'
import type { Resort, SnowQualitySummary } from '../../api/types'
import { QualityBadge } from './QualityBadge'
import { ResortLogo } from './ResortLogo'
import { countryFlag, regionDisplayName } from '../../utils/format'
import { useUnits } from '../../hooks/useUnits'

interface ResortCardProps {
  resort: Resort
  quality?: SnowQualitySummary
  isFavorite?: boolean
  onToggleFavorite?: (id: string) => void
  distanceKm?: number | null
}

export function ResortCard({ resort, quality, isFavorite, onToggleFavorite, distanceKm }: ResortCardProps) {
  const { formatTemp, formatSnow } = useUnits()
  return (
    <Link
      to={`/resort/${resort.resort_id}`}
      className="block bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow group"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <ResortLogo name={resort.name} officialWebsite={resort.official_website} size={36} className="shrink-0" />
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors truncate">
              {resort.name}
            </h3>
            <p className="text-sm text-gray-500 truncate">
              {countryFlag(resort.country)} {regionDisplayName(resort.region)}, {resort.country}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <QualityBadge
            quality={quality?.overall_quality}
            score={quality?.snow_score}
            size="sm"
          />
          {onToggleFavorite && (
            <button
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onToggleFavorite(resort.resort_id)
              }}
              className="p-1 -mr-1 rounded-full hover:bg-gray-100 transition-colors"
              aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
            >
              <Heart
                className={`w-4 h-4 transition-colors ${isFavorite ? 'fill-red-500 text-red-500' : 'text-gray-300 hover:text-red-400'}`}
              />
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="flex items-center gap-1.5 text-sm text-gray-600">
          <Snowflake className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          <span className="truncate">
            {quality?.snowfall_fresh_cm != null
              ? formatSnow(quality.snowfall_fresh_cm)
              : '--'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-sm text-gray-600">
          <Thermometer className="w-3.5 h-3.5 text-orange-400 shrink-0" />
          <span className="truncate">
            {quality?.temperature_c != null ? formatTemp(quality.temperature_c) : '--'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-sm text-gray-600">
          <Wind className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          <span className="truncate">
            {quality?.snow_depth_cm != null
              ? formatSnow(quality.snow_depth_cm)
              : '--'}
          </span>
        </div>
      </div>

      {/* Distance badge */}
      {distanceKm != null && (
        <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-gray-50 text-sm text-gray-500">
          <Navigation className="w-3.5 h-3.5" />
          {distanceKm < 100
            ? `${Math.round(distanceKm)} km`
            : `${Math.round(distanceKm)} km`}
        </div>
      )}

      {/* Pass badges */}
      {(resort.epic_pass || resort.ikon_pass || resort.indy_pass) && (
        <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-gray-50">
          {resort.epic_pass && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 font-medium">
              Epic
            </span>
          )}
          {resort.ikon_pass && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 font-medium">
              Ikon
            </span>
          )}
          {resort.indy_pass && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-700 font-medium">
              Indy
            </span>
          )}
        </div>
      )}
    </Link>
  )
}
