import {
  Snowflake,
  Thermometer,
  Clock,
  AlertTriangle,
  TrendingUp,
  Layers,
} from 'lucide-react'
import type { WeatherCondition, SnowQuality } from '../../api/types'
import { QualityBadge } from './QualityBadge'
import { useUnits } from '../../hooks/useUnits'

interface SnowDetailsCardProps {
  condition: WeatherCondition
  explanation?: string | null
}

function formatHoursAgo(hours: number | null | undefined): string {
  if (hours == null) return '--'
  if (hours < 1) return 'Less than 1h ago'
  if (hours < 24) return `${Math.round(hours)}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ${Math.round(hours % 24)}h ago`
}

export function SnowDetailsCard({ condition, explanation }: SnowDetailsCardProps) {
  const { formatTemp, formatSnow } = useUnits()
  const thinCoverage = condition.snow_depth_cm != null && condition.snow_depth_cm < 50

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">
        Snow Conditions
      </h3>

      {/* Quality + Score row */}
      <div className="flex items-center gap-3">
        <QualityBadge
          quality={condition.snow_quality as SnowQuality}
          score={condition.quality_score != null ? Math.round(condition.quality_score * 10) : null}
          size="md"
        />
        {condition.confidence_level && (
          <span className="text-xs text-gray-400">
            {condition.confidence_level} confidence
          </span>
        )}
      </div>

      {/* Explanation */}
      {explanation && (
        <p className="text-sm text-gray-600 bg-blue-50 rounded-lg px-3 py-2">
          {explanation}
        </p>
      )}

      {/* Grid of snow details */}
      <div className="grid grid-cols-2 gap-3">
        {/* Temperature */}
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
            <Thermometer className="w-3.5 h-3.5" />
            Temperature
          </div>
          <p className="text-lg font-bold text-gray-900">
            {formatTemp(condition.current_temp_celsius)}
          </p>
          {condition.currently_warming && (
            <div className="flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3 text-orange-500" />
              <span className="text-xs text-orange-600 font-medium">Currently warming</span>
            </div>
          )}
        </div>

        {/* Fresh Snow */}
        <div className="bg-blue-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-blue-600 mb-1">
            <Snowflake className="w-3.5 h-3.5" />
            Fresh Snow
          </div>
          <p className="text-lg font-bold text-gray-900">
            {formatSnow(condition.fresh_snow_cm)}
          </p>
          {condition.hours_since_last_snowfall != null && (
            <p className="text-xs text-gray-500 mt-1">
              Last snow: {formatHoursAgo(condition.hours_since_last_snowfall)}
            </p>
          )}
        </div>

        {/* Snow Depth */}
        <div className={`rounded-lg p-3 ${thinCoverage ? 'bg-orange-50' : 'bg-gray-50'}`}>
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
            <Layers className="w-3.5 h-3.5" />
            Base Depth
          </div>
          <p className="text-lg font-bold text-gray-900">
            {condition.snow_depth_cm != null ? formatSnow(condition.snow_depth_cm) : '--'}
          </p>
          {thinCoverage && (
            <div className="flex items-center gap-1 mt-1">
              <AlertTriangle className="w-3 h-3 text-orange-500" />
              <span className="text-xs text-orange-600 font-medium">Thin coverage</span>
            </div>
          )}
        </div>

        {/* Snow Since Freeze */}
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
            <Snowflake className="w-3.5 h-3.5" />
            Snow Since Freeze
          </div>
          <p className="text-lg font-bold text-gray-900">
            {formatSnow(condition.snowfall_after_freeze_cm)}
          </p>
          {condition.last_freeze_thaw_hours_ago != null && (
            <p className="text-xs text-gray-500 mt-1">
              Last freeze: {formatHoursAgo(condition.last_freeze_thaw_hours_ago)}
            </p>
          )}
        </div>

        {/* Surface conditions */}
        {condition.weather_description && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
              <Clock className="w-3.5 h-3.5" />
              Current Weather
            </div>
            <p className="text-sm font-medium text-gray-900">
              {condition.weather_description}
            </p>
          </div>
        )}

        {/* 24h/48h/72h Snowfall */}
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
            <Snowflake className="w-3.5 h-3.5 text-blue-400" />
            Recent Snowfall
          </div>
          <div className="grid grid-cols-3 gap-2 mt-1">
            <div>
              <p className="text-xs text-gray-400">24h</p>
              <p className="text-sm font-bold text-gray-900">{formatSnow(condition.snowfall_24h_cm)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">48h</p>
              <p className="text-sm font-bold text-gray-900">{formatSnow(condition.snowfall_48h_cm)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">72h</p>
              <p className="text-sm font-bold text-gray-900">{formatSnow(condition.snowfall_72h_cm)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
