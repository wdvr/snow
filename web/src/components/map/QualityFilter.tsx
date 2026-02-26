import type { SnowQuality } from '../../api/types'

export type QualityTier = 'all' | 'powder' | 'excellent' | 'good' | 'mediocre'

interface QualityFilterProps {
  selected: QualityTier
  onChange: (tier: QualityTier) => void
}

const tiers: { key: QualityTier; label: string; qualities: SnowQuality[] }[] = [
  { key: 'all', label: 'All', qualities: [] },
  {
    key: 'powder',
    label: 'Powder+',
    qualities: ['champagne_powder', 'powder_day'],
  },
  {
    key: 'excellent',
    label: 'Excellent+',
    qualities: ['champagne_powder', 'powder_day', 'excellent', 'great'],
  },
  {
    key: 'good',
    label: 'Good+',
    qualities: ['champagne_powder', 'powder_day', 'excellent', 'great', 'good', 'decent'],
  },
  {
    key: 'mediocre',
    label: 'Fair+',
    qualities: [
      'champagne_powder',
      'powder_day',
      'excellent',
      'great',
      'good',
      'decent',
      'mediocre',
      'fair',
    ],
  },
]

export function qualitiesForTier(tier: QualityTier): SnowQuality[] | null {
  if (tier === 'all') return null
  return tiers.find((t) => t.key === tier)?.qualities ?? null
}

export function QualityFilter({ selected, onChange }: QualityFilterProps) {
  return (
    <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
      {tiers.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
            selected === key
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-white/90 text-gray-700 hover:bg-white border border-gray-200'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
