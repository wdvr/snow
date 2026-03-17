import type { WeatherCondition, SnowQuality } from '../../api/types'
import { getQualityColor } from '../../utils/colors'
import { useUnits } from '../../hooks/useUnits'

interface ElevationProfileProps {
  conditions: WeatherCondition[]
  elevationMeters: Record<string, number>
  selectedLevel?: string
  onSelectLevel?: (level: string) => void
}

const LEVEL_ORDER = ['top', 'mid', 'base']
const LEVEL_LABELS: Record<string, string> = {
  top: 'Summit',
  mid: 'Mid',
  base: 'Base',
}

export function ElevationProfile({ conditions, elevationMeters, selectedLevel, onSelectLevel }: ElevationProfileProps) {
  const { formatTemp, formatSnow } = useUnits()
  const sorted = [...conditions].sort(
    (a, b) => LEVEL_ORDER.indexOf(a.elevation_level) - LEVEL_ORDER.indexOf(b.elevation_level),
  )

  if (sorted.length === 0) return null

  // Mountain profile SVG dimensions
  const width = 280
  const height = 200
  const padding = { top: 10, right: 100, bottom: 10, left: 10 }
  const profileWidth = width - padding.left - padding.right
  const profileHeight = height - padding.top - padding.bottom

  // Elevation range
  const elevations = sorted.map((c) => elevationMeters[c.elevation_level] ?? 0)
  const minElev = Math.min(...elevations)
  const maxElev = Math.max(...elevations)
  const elevRange = maxElev - minElev || 1

  // Mountain profile path points
  const getY = (elev: number) => {
    const normalized = (elev - minElev) / elevRange
    return padding.top + profileHeight * (1 - normalized)
  }

  // Mountain silhouette
  const peakX = padding.left + profileWidth * 0.35
  const baseY = padding.top + profileHeight
  const peakY = padding.top + 5

  const mountainPath = `
    M ${padding.left} ${baseY}
    L ${peakX - 20} ${peakY + 30}
    L ${peakX} ${peakY}
    L ${peakX + 25} ${peakY + 25}
    L ${padding.left + profileWidth} ${baseY}
    Z
  `

  return (
    <div className="flex items-start gap-2">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
        {/* Mountain silhouette background */}
        <path d={mountainPath} fill="#e5e7eb" opacity={0.4} />

        {/* Elevation bands with quality colors */}
        {sorted.map((condition, i) => {
          const elev = elevationMeters[condition.elevation_level] ?? 0
          const y = getY(elev)
          const color = getQualityColor(condition.snow_quality as SnowQuality)
          const isSelected = selectedLevel === condition.elevation_level
          const nextY = i < sorted.length - 1
            ? getY(elevationMeters[sorted[i + 1].elevation_level] ?? 0)
            : baseY
          const bandHeight = nextY - y

          // Clip band to mountain shape
          const clipId = `clip-${condition.elevation_level}`
          return (
            <g key={condition.elevation_level}>
              <defs>
                <clipPath id={clipId}>
                  <path d={mountainPath} />
                </clipPath>
              </defs>
              {/* Colored band */}
              <rect
                x={padding.left}
                y={y}
                width={profileWidth}
                height={bandHeight}
                fill={color.hex}
                opacity={isSelected ? 0.6 : 0.35}
                clipPath={`url(#${clipId})`}
              />
              {/* Elevation line */}
              <line
                x1={padding.left}
                y1={y}
                x2={padding.left + profileWidth + 5}
                y2={y}
                stroke={color.hex}
                strokeWidth={isSelected ? 2 : 1}
                strokeDasharray={isSelected ? 'none' : '4 2'}
                opacity={0.8}
              />
              {/* Label */}
              <g
                onClick={() => onSelectLevel?.(condition.elevation_level)}
                className="cursor-pointer"
              >
                <text
                  x={padding.left + profileWidth + 10}
                  y={y + 4}
                  fontSize={isSelected ? 12 : 11}
                  fontWeight={isSelected ? 700 : 500}
                  fill={isSelected ? color.hex : '#6b7280'}
                >
                  {LEVEL_LABELS[condition.elevation_level] ?? condition.elevation_level}
                </text>
                <text
                  x={padding.left + profileWidth + 10}
                  y={y + 18}
                  fontSize={10}
                  fill="#9ca3af"
                >
                  {elev}m
                </text>
                {/* Quality dot */}
                <circle
                  cx={padding.left + profileWidth + 80}
                  cy={y + 6}
                  r={5}
                  fill={color.hex}
                />
              </g>
            </g>
          )
        })}

        {/* Mountain outline */}
        <path d={mountainPath} fill="none" stroke="#9ca3af" strokeWidth={1.5} opacity={0.5} />
      </svg>

      {/* Conditions summary next to profile */}
      <div className="flex-1 min-w-0 space-y-2 pt-1">
        {sorted.map((condition) => {
          const color = getQualityColor(condition.snow_quality as SnowQuality)
          const isSelected = selectedLevel === condition.elevation_level
          return (
            <button
              key={condition.elevation_level}
              onClick={() => onSelectLevel?.(condition.elevation_level)}
              className={`w-full text-left rounded-lg p-2.5 transition-colors ${
                isSelected
                  ? 'bg-gray-50 ring-1 ring-gray-200'
                  : 'hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: color.hex }} />
                <span className="text-xs font-medium text-gray-900 capitalize">
                  {condition.snow_quality?.replace(/_/g, ' ') ?? 'Unknown'}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span>{formatTemp(condition.current_temp_celsius)}</span>
                <span>{formatSnow(condition.fresh_snow_cm)} fresh</span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
