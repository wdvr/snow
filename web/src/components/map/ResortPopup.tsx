import { Link } from 'react-router-dom'
import { Thermometer, Snowflake, ArrowRight } from 'lucide-react'
import type { Resort, SnowQualitySummary } from '../../api/types'
import { QualityBadge } from '../resort/QualityBadge'
import { ResortLogo } from '../resort/ResortLogo'
import { countryFlag } from '../../utils/format'
import { useUnits } from '../../hooks/useUnits'

interface ResortPopupProps {
  resort: Resort
  quality?: SnowQualitySummary
}

export function ResortPopup({ resort, quality }: ResortPopupProps) {
  const { formatTemp, formatSnow } = useUnits()
  return (
    <div className="min-w-[200px] max-w-[260px]">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <ResortLogo name={resort.name} officialWebsite={resort.official_website} logoUrl={resort.logo_url} size={28} className="shrink-0" />
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 text-sm leading-tight">
              {resort.name}
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {countryFlag(resort.country)} {resort.country}
            </p>
          </div>
        </div>
        <QualityBadge
          quality={quality?.overall_quality}
          score={quality?.snow_score}
          size="sm"
        />
      </div>

      <div className="flex items-center gap-4 mb-3">
        <div className="flex items-center gap-1 text-xs text-gray-600">
          <Thermometer className="w-3 h-3 text-orange-400" />
          <span>{quality?.temperature_c != null ? formatTemp(quality.temperature_c) : '--'}</span>
        </div>
        <div className="flex items-center gap-1 text-xs text-gray-600">
          <Snowflake className="w-3 h-3 text-blue-400" />
          <span>
            {quality?.snowfall_fresh_cm != null ? formatSnow(quality.snowfall_fresh_cm) : '--'}
          </span>
        </div>
      </div>

      {/* Pass badges */}
      {(resort.epic_pass || resort.ikon_pass || resort.indy_pass) && (
        <div className="flex items-center gap-1.5 mb-3">
          {resort.epic_pass && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-50 text-purple-700 font-medium">
              Epic
            </span>
          )}
          {resort.ikon_pass && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-orange-50 text-orange-700 font-medium">
              Ikon
            </span>
          )}
          {resort.indy_pass && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-50 text-green-700 font-medium">
              Indy
            </span>
          )}
        </div>
      )}

      <Link
        to={`/resort/${resort.resort_id}`}
        className="flex items-center justify-center gap-1.5 w-full px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors"
      >
        View Details
        <ArrowRight className="w-3 h-3" />
      </Link>
    </div>
  )
}
