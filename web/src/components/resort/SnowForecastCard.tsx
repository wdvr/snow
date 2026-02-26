import { Snowflake, AlertTriangle, CloudSnow } from 'lucide-react'
import type { WeatherCondition } from '../../api/types'
import { useUnits } from '../../hooks/useUnits'

interface SnowForecastCardProps {
  condition: WeatherCondition
}

type StormLevel = 'heavy' | 'light' | 'none'

function getStormLevel(cm72h: number): StormLevel {
  if (cm72h >= 30) return 'heavy'
  if (cm72h >= 5) return 'light'
  return 'none'
}

function StormBadge({ level }: { level: StormLevel }) {
  if (level === 'none') return null

  if (level === 'heavy') {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 border border-red-200 rounded-lg">
        <AlertTriangle className="w-4 h-4 text-red-500" />
        <span className="text-sm font-semibold text-red-700">Heavy Snow Alert</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg">
      <CloudSnow className="w-4 h-4 text-blue-500" />
      <span className="text-sm font-semibold text-blue-700">Snow Expected</span>
    </div>
  )
}

function SnowBar({ cm, maxCm }: { cm: number; maxCm: number }) {
  const pct = maxCm > 0 ? Math.min((cm / maxCm) * 100, 100) : 0
  const intensity =
    cm >= 30 ? 'bg-blue-700' :
    cm >= 15 ? 'bg-blue-600' :
    cm >= 5 ? 'bg-blue-500' :
    cm > 0 ? 'bg-blue-300' :
    'bg-gray-200'

  return (
    <div className="w-full bg-gray-100 rounded-full h-3">
      <div
        className={`h-3 rounded-full transition-all ${intensity}`}
        style={{ width: `${Math.max(pct, 2)}%` }}
      />
    </div>
  )
}

export function SnowForecastCard({ condition }: SnowForecastCardProps) {
  const { formatSnow } = useUnits()
  const periods = [
    { label: '24h', cm: condition.predicted_snow_24h_cm },
    { label: '48h', cm: condition.predicted_snow_48h_cm },
    { label: '72h', cm: condition.predicted_snow_72h_cm },
  ]

  const maxCm = Math.max(...periods.map((p) => p.cm), 1)
  const stormLevel = getStormLevel(condition.predicted_snow_72h_cm)

  const hasAnySnow = periods.some((p) => p.cm > 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
          <Snowflake className="w-4 h-4 text-blue-400" />
          Snow Forecast
        </h3>
        <StormBadge level={stormLevel} />
      </div>

      {hasAnySnow ? (
        <div className="space-y-3">
          {periods.map((period) => (
            <div key={period.label} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600 font-medium">{period.label}</span>
                <span className={`font-bold ${
                  period.cm >= 30 ? 'text-blue-700' :
                  period.cm >= 15 ? 'text-blue-600' :
                  period.cm >= 5 ? 'text-blue-500' :
                  period.cm > 0 ? 'text-blue-400' :
                  'text-gray-400'
                }`}>
                  {formatSnow(period.cm)}
                </span>
              </div>
              <SnowBar cm={period.cm} maxCm={maxCm} />
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500 py-4 text-center">
          No snow in the forecast
        </p>
      )}
    </div>
  )
}
