import { useMemo, useState } from 'react'
import {
  Clock,
  Thermometer,
  Snowflake,
  Wind,
  Eye,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import type { TimelinePoint } from '../../api/types'
import { useUnits } from '../../hooks/useUnits'
import { getQualityColor } from '../../utils/colors'
import { formatQuality, formatVisibility } from '../../utils/format'
import type { SnowQuality } from '../../api/types'

interface HourlyTimelineProps {
  timeline: TimelinePoint[]
}

/** Group timeline points by date for day-by-day navigation */
function groupByDate(points: TimelinePoint[]): Map<string, TimelinePoint[]> {
  const groups = new Map<string, TimelinePoint[]>()
  for (const p of points) {
    const existing = groups.get(p.date)
    if (existing) {
      existing.push(p)
    } else {
      groups.set(p.date, [p])
    }
  }
  return groups
}

function formatHour(timeLabel: string, hour: number): string {
  if (timeLabel && timeLabel !== 'unknown') {
    return timeLabel.charAt(0).toUpperCase() + timeLabel.slice(1)
  }
  const h = hour % 12 || 12
  const ampm = hour < 12 ? 'AM' : 'PM'
  return `${h} ${ampm}`
}

function weatherIcon(code: number | null): string {
  if (code == null) return ''
  if (code <= 3) return '\u2600\uFE0F' // sun
  if (code <= 48) return '\u2601\uFE0F' // cloud
  if (code <= 67) return '\uD83C\uDF27\uFE0F' // rain
  if (code <= 77) return '\u2744\uFE0F' // snow
  if (code <= 86) return '\uD83C\uDF28\uFE0F' // heavy snow
  return '\u26C8\uFE0F' // storm
}

export function HourlyTimeline({ timeline }: HourlyTimelineProps) {
  const { formatTemp, formatSnow } = useUnits()
  const [selectedDayIndex, setSelectedDayIndex] = useState(0)

  const dayGroups = useMemo(() => groupByDate(timeline), [timeline])
  const dates = useMemo(() => Array.from(dayGroups.keys()), [dayGroups])

  if (dates.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No hourly forecast data available
      </div>
    )
  }

  const currentDate = dates[selectedDayIndex]
  const points = dayGroups.get(currentDate) ?? []
  const dateLabel = new Date(currentDate).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  })

  // Day summary
  const totalSnow = points.reduce((sum, p) => sum + p.snowfall_cm, 0)
  const minTemp = Math.min(...points.map((p) => p.temperature_c))
  const maxTemp = Math.max(...points.map((p) => p.temperature_c))

  return (
    <div className="w-full">
      <h4 className="text-sm font-medium text-gray-500 mb-4 flex items-center gap-2">
        <Clock className="w-4 h-4" />
        Hourly Forecast
      </h4>

      {/* Day selector */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setSelectedDayIndex(Math.max(0, selectedDayIndex - 1))}
          disabled={selectedDayIndex === 0}
          className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-5 h-5 text-gray-600" />
        </button>

        <div className="text-center">
          <p className="font-semibold text-gray-900">{dateLabel}</p>
          <div className="flex items-center justify-center gap-3 text-xs text-gray-500 mt-0.5">
            <span className="flex items-center gap-1">
              <Thermometer className="w-3 h-3" />
              {formatTemp(minTemp)} / {formatTemp(maxTemp)}
            </span>
            {totalSnow > 0 && (
              <span className="flex items-center gap-1">
                <Snowflake className="w-3 h-3 text-blue-500" />
                {formatSnow(totalSnow)}
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => setSelectedDayIndex(Math.min(dates.length - 1, selectedDayIndex + 1))}
          disabled={selectedDayIndex === dates.length - 1}
          className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-5 h-5 text-gray-600" />
        </button>
      </div>

      {/* Day pills */}
      <div className="flex gap-1.5 overflow-x-auto pb-3 mb-3 scrollbar-none">
        {dates.map((date, i) => {
          const dayPoints = dayGroups.get(date) ?? []
          const daySnow = dayPoints.reduce((s, p) => s + p.snowfall_cm, 0)
          const dayLabel = new Date(date).toLocaleDateString('en-US', {
            weekday: 'short',
            day: 'numeric',
          })
          return (
            <button
              key={date}
              onClick={() => setSelectedDayIndex(i)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                i === selectedDayIndex
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {dayLabel}
              {daySnow > 0 && (
                <span className="ml-1 opacity-75">
                  {'\u2744\uFE0F'}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Hourly cards */}
      <div className="space-y-2">
        {points.map((point, i) => {
          const qualityColors = getQualityColor(point.snow_quality as SnowQuality)
          return (
            <div
              key={`${point.date}-${point.hour}-${i}`}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
            >
              {/* Time */}
              <div className="w-16 flex-shrink-0">
                <span className="text-sm font-semibold text-gray-800">
                  {formatHour(point.time_label, point.hour)}
                </span>
              </div>

              {/* Weather icon */}
              <div className="w-6 flex-shrink-0 text-center">
                <span className="text-base">{weatherIcon(point.weather_code)}</span>
              </div>

              {/* Temperature */}
              <div className="w-12 flex-shrink-0 text-right">
                <span className="text-sm font-medium text-gray-700">
                  {formatTemp(point.temperature_c)}
                </span>
              </div>

              {/* Snowfall */}
              <div className="w-16 flex-shrink-0">
                {point.snowfall_cm > 0 ? (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                    <Snowflake className="w-3 h-3" />
                    {formatSnow(point.snowfall_cm)}
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">--</span>
                )}
              </div>

              {/* Quality badge */}
              <div className="flex-1 min-w-0">
                <span
                  className="inline-block text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{
                    backgroundColor: `${qualityColors.hex}20`,
                    color: qualityColors.hex,
                  }}
                >
                  {formatQuality(point.snow_quality)}
                </span>
              </div>

              {/* Wind */}
              {point.wind_speed_kmh != null && (
                <div className="hidden sm:flex items-center gap-1 text-xs text-gray-500 w-16 flex-shrink-0">
                  <Wind className="w-3 h-3" />
                  {Math.round(point.wind_speed_kmh)} km/h
                </div>
              )}

              {/* Visibility */}
              {point.visibility_m != null && point.visibility_m < 5000 && (
                <div className="hidden sm:flex items-center gap-1 text-xs text-orange-500 w-16 flex-shrink-0">
                  <Eye className="w-3 h-3" />
                  {formatVisibility(point.visibility_m)}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Legend note */}
      {points.some((p) => p.is_forecast) && (
        <p className="text-xs text-gray-400 mt-3 text-center">
          Forecast data — conditions may vary
        </p>
      )}
    </div>
  )
}
