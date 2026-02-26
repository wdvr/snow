import { Mountain } from 'lucide-react'
import type { WeatherCondition, SnowQuality } from '../../api/types'
import { QualityBadge } from './QualityBadge'
import { useUnits } from '../../hooks/useUnits'

interface AllElevationsSummaryProps {
  conditions: WeatherCondition[]
  elevationMeters?: Record<string, number>
}

const LEVEL_ORDER = ['top', 'mid', 'base']
const LEVEL_LABELS: Record<string, string> = {
  top: 'Summit',
  mid: 'Mid-Mountain',
  base: 'Base',
}

export function AllElevationsSummary({ conditions, elevationMeters }: AllElevationsSummaryProps) {
  const { formatTemp, formatSnow } = useUnits()
  const sorted = [...conditions].sort(
    (a, b) => LEVEL_ORDER.indexOf(a.elevation_level) - LEVEL_ORDER.indexOf(b.elevation_level),
  )

  if (sorted.length <= 1) return null

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
        <Mountain className="w-4 h-4" />
        All Elevations
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {sorted.map((condition) => (
          <div
            key={condition.elevation_level}
            className="bg-gray-50 rounded-lg p-4 space-y-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">
                  {LEVEL_LABELS[condition.elevation_level] ?? condition.elevation_level}
                </p>
                {elevationMeters?.[condition.elevation_level] != null && (
                  <p className="text-xs text-gray-400">
                    {elevationMeters[condition.elevation_level]}m
                  </p>
                )}
              </div>
              <QualityBadge
                quality={condition.snow_quality as SnowQuality}
                score={condition.quality_score != null ? Math.round(condition.quality_score * 10) : null}
                size="sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="text-xs text-gray-400">Temp</p>
                <p className="font-medium text-gray-700">{formatTemp(condition.current_temp_celsius)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Fresh Snow</p>
                <p className="font-medium text-gray-700">{formatSnow(condition.fresh_snow_cm)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Base Depth</p>
                <p className="font-medium text-gray-700">
                  {condition.snow_depth_cm != null ? formatSnow(condition.snow_depth_cm) : '--'}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">24h Snow</p>
                <p className="font-medium text-gray-700">{formatSnow(condition.snowfall_24h_cm)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
