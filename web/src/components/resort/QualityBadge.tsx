import type { SnowQuality } from '../../api/types'
import { getQualityColor } from '../../utils/colors'
import { formatQuality } from '../../utils/format'

interface QualityBadgeProps {
  quality: SnowQuality | string | undefined
  score?: number | null
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function QualityBadge({
  quality,
  score,
  size = 'md',
  showLabel = true,
}: QualityBadgeProps) {
  const colors = getQualityColor(quality as SnowQuality)

  if (size === 'lg') {
    return (
      <div className="flex flex-col items-center gap-1">
        {score != null && (
          <span
            className={`text-3xl font-bold ${colors.text}`}
          >
            {score}
          </span>
        )}
        <span
          className={`inline-flex items-center gap-1.5 rounded-full font-semibold text-white ${colors.bg} px-4 py-1.5 text-base`}
        >
          {showLabel && <span>{formatQuality(quality)}</span>}
        </span>
      </div>
    )
  }

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base',
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold text-white ${colors.bg} ${sizeClasses[size]}`}
    >
      {showLabel && <span>{formatQuality(quality)}</span>}
      {score != null && <span className="opacity-90">{score}</span>}
    </span>
  )
}
