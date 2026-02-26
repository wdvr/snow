import {
  Thermometer,
  Droplets,
  Wind,
  Eye,
  Cloud,
} from 'lucide-react'
import type { WeatherCondition } from '../../api/types'
import { formatWind, formatVisibility, visibilitySeverity } from '../../utils/format'
import { useUnits } from '../../hooks/useUnits'

interface WeatherDetailsCardProps {
  condition: WeatherCondition
}

export function WeatherDetailsCard({ condition }: WeatherDetailsCardProps) {
  const { formatTemp } = useUnits()
  const maxGust = condition.max_wind_gust_24h ?? condition.max_wind_gust_24h_kmh

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">
        Weather Details
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {/* Min/Max Temperature */}
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
            <Thermometer className="w-3.5 h-3.5" />
            Min / Max Temp
          </div>
          <p className="text-sm font-bold text-gray-900">
            {formatTemp(condition.min_temp_celsius)} / {formatTemp(condition.max_temp_celsius)}
          </p>
        </div>

        {/* Humidity */}
        {condition.humidity_percent != null && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
              <Droplets className="w-3.5 h-3.5" />
              Humidity
            </div>
            <p className="text-sm font-bold text-gray-900">
              {Math.round(condition.humidity_percent)}%
            </p>
          </div>
        )}

        {/* Wind */}
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
            <Wind className="w-3.5 h-3.5" />
            Wind Speed
          </div>
          <p className="text-sm font-bold text-gray-900">
            {formatWind(condition.wind_speed_kmh)}
          </p>
          {condition.wind_gust_kmh != null && condition.wind_gust_kmh > 0 && (
            <p className="text-xs text-gray-500 mt-0.5">
              Gust: {Math.round(condition.wind_gust_kmh)} km/h
            </p>
          )}
        </div>

        {/* Max Gust 24h */}
        {maxGust != null && maxGust > 0 && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
              <Wind className="w-3.5 h-3.5 text-orange-400" />
              Max Gust (24h)
            </div>
            <p className="text-sm font-bold text-gray-900">
              {Math.round(maxGust)} km/h
            </p>
          </div>
        )}

        {/* Visibility */}
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
            <Eye className="w-3.5 h-3.5" />
            Visibility
          </div>
          <p className={`text-sm font-bold ${visibilitySeverity(condition.visibility_m) || 'text-gray-900'}`}>
            {formatVisibility(condition.visibility_m)}
          </p>
        </div>

        {/* Min Visibility 24h */}
        {condition.min_visibility_24h_m != null && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
              <Eye className="w-3.5 h-3.5 text-orange-400" />
              Min Visibility (24h)
            </div>
            <p className={`text-sm font-bold ${visibilitySeverity(condition.min_visibility_24h_m) || 'text-gray-900'}`}>
              {formatVisibility(condition.min_visibility_24h_m)}
            </p>
          </div>
        )}

        {/* Weather Description */}
        {condition.weather_description && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
              <Cloud className="w-3.5 h-3.5" />
              Description
            </div>
            <p className="text-sm font-bold text-gray-900">
              {condition.weather_description}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
