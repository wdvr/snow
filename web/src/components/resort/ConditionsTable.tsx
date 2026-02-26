import { Mountain, Thermometer, Snowflake, Wind, Layers, Eye } from 'lucide-react'
import type { WeatherCondition } from '../../api/types'
import { QualityBadge } from './QualityBadge'
import { formatTemp, formatSnowCm, formatWind, formatVisibility, visibilitySeverity } from '../../utils/format'

interface ConditionsTableProps {
  conditions: WeatherCondition[]
}

const LEVEL_ORDER = ['top', 'mid', 'base']
const LEVEL_LABELS: Record<string, string> = {
  top: 'Summit',
  mid: 'Mid-Mountain',
  base: 'Base',
}

export function ConditionsTable({ conditions }: ConditionsTableProps) {
  const sorted = [...conditions].sort(
    (a, b) => LEVEL_ORDER.indexOf(a.elevation_level) - LEVEL_ORDER.indexOf(b.elevation_level),
  )

  if (sorted.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No conditions data available
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-gray-500 border-b border-gray-100">
            <th className="pb-3 pr-4 font-medium">
              <div className="flex items-center gap-1.5">
                <Mountain className="w-4 h-4" />
                Elevation
              </div>
            </th>
            <th className="pb-3 px-4 font-medium">Quality</th>
            <th className="pb-3 px-4 font-medium">
              <div className="flex items-center gap-1.5">
                <Thermometer className="w-4 h-4" />
                Temp
              </div>
            </th>
            <th className="pb-3 px-4 font-medium">
              <div className="flex items-center gap-1.5">
                <Snowflake className="w-4 h-4" />
                Fresh
              </div>
            </th>
            <th className="pb-3 px-4 font-medium">
              <div className="flex items-center gap-1.5">
                <Layers className="w-4 h-4" />
                Depth
              </div>
            </th>
            <th className="pb-3 px-4 font-medium">
              <div className="flex items-center gap-1.5">
                <Wind className="w-4 h-4" />
                Wind
              </div>
            </th>
            <th className="pb-3 px-4 font-medium">
              <div className="flex items-center gap-1.5">
                <Eye className="w-4 h-4" />
                Visibility
              </div>
            </th>
            <th className="pb-3 px-4 font-medium">24h Snow</th>
            <th className="pb-3 pl-4 font-medium">
              <div className="flex items-center gap-1.5">
                <Snowflake className="w-4 h-4 text-blue-400" />
                48h Forecast
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((condition) => (
            <tr
              key={condition.elevation_level}
              className="border-b border-gray-50 last:border-0"
            >
              <td className="py-3 pr-4">
                <span className="font-medium text-gray-900">
                  {LEVEL_LABELS[condition.elevation_level] ?? condition.elevation_level}
                </span>
              </td>
              <td className="py-3 px-4">
                <QualityBadge
                  quality={condition.snow_quality}
                  score={condition.quality_score != null ? Math.round(condition.quality_score * 10) : null}
                  size="sm"
                />
              </td>
              <td className="py-3 px-4 text-sm text-gray-700">
                {formatTemp(condition.current_temp_celsius)}
              </td>
              <td className="py-3 px-4 text-sm text-gray-700">
                {formatSnowCm(condition.fresh_snow_cm)}
              </td>
              <td className="py-3 px-4 text-sm text-gray-700">
                {condition.snow_depth_cm != null
                  ? formatSnowCm(condition.snow_depth_cm)
                  : '--'}
              </td>
              <td className="py-3 px-4 text-sm text-gray-700">
                <span>{formatWind(condition.wind_speed_kmh)}</span>
                {condition.wind_gust_kmh != null && condition.wind_gust_kmh > 0 && (
                  <span className="text-xs text-gray-400 ml-1">
                    (gust {Math.round(condition.wind_gust_kmh)})
                  </span>
                )}
              </td>
              <td className={`py-3 px-4 text-sm text-gray-700 ${visibilitySeverity(condition.visibility_m)}`}>
                {formatVisibility(condition.visibility_m)}
              </td>
              <td className="py-3 px-4 text-sm text-gray-700">
                {formatSnowCm(condition.snowfall_24h_cm)}
              </td>
              <td className="py-3 pl-4 text-sm text-gray-700">
                {condition.predicted_snow_48h_cm != null && condition.predicted_snow_48h_cm > 0 ? (
                  <span className="text-blue-600 font-medium">
                    {formatSnowCm(condition.predicted_snow_48h_cm)}
                  </span>
                ) : (
                  <span className="text-gray-400">--</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
