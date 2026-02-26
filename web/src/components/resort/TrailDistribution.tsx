import type { Resort } from '../../api/types'

interface TrailDistributionProps {
  resort: Resort
}

export function TrailDistribution({ resort }: TrailDistributionProps) {
  const green = resort.green_runs_pct ?? 0
  const blue = resort.blue_runs_pct ?? 0
  const black = resort.black_runs_pct ?? 0
  const total = green + blue + black

  if (total === 0) return null

  return (
    <div className="mt-4">
      <h3 className="text-sm font-medium text-gray-700 mb-2">Trail Difficulty</h3>
      {/* Stacked bar */}
      <div className="flex h-5 rounded-full overflow-hidden">
        {green > 0 && (
          <div
            className="bg-green-500"
            style={{ width: `${(green / total) * 100}%` }}
          />
        )}
        {blue > 0 && (
          <div
            className="bg-blue-500"
            style={{ width: `${(blue / total) * 100}%` }}
          />
        )}
        {black > 0 && (
          <div
            className="bg-gray-900"
            style={{ width: `${(black / total) * 100}%` }}
          />
        )}
      </div>
      {/* Labels */}
      <div className="flex justify-between mt-1.5 text-xs text-gray-500">
        {green > 0 && (
          <div className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
            Green {green}%
          </div>
        )}
        {blue > 0 && (
          <div className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-blue-500" />
            Blue {blue}%
          </div>
        )}
        {black > 0 && (
          <div className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-gray-900" />
            Black {black}%
          </div>
        )}
      </div>
    </div>
  )
}
