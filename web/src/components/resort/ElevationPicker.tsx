import { Mountain } from 'lucide-react'

interface ElevationPickerProps {
  levels: string[]
  selected: string
  onChange: (level: string) => void
  elevationMeters?: Record<string, number>
}

const LEVEL_LABELS: Record<string, string> = {
  top: 'Summit',
  mid: 'Mid',
  base: 'Base',
}

const LEVEL_ORDER = ['top', 'mid', 'base']

export function ElevationPicker({ levels, selected, onChange, elevationMeters }: ElevationPickerProps) {
  const sorted = [...levels].sort(
    (a, b) => LEVEL_ORDER.indexOf(a) - LEVEL_ORDER.indexOf(b),
  )

  if (sorted.length <= 1) return null

  return (
    <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-lg">
      {sorted.map((level) => (
        <button
          key={level}
          onClick={() => onChange(level)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            selected === level
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Mountain className="w-3.5 h-3.5" />
          <span>{LEVEL_LABELS[level] ?? level}</span>
          {elevationMeters?.[level] != null && (
            <span className="text-xs text-gray-400">{elevationMeters[level]}m</span>
          )}
        </button>
      ))}
    </div>
  )
}
