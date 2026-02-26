import type { SnowQuality } from '../../api/types'

// Full quality scale from best to worst
const QUALITY_SCALE: SnowQuality[] = [
  'champagne_powder',
  'powder_day',
  'excellent',
  'great',
  'good',
  'decent',
  'mediocre',
  'fair',
  'poor',
  'slushy',
  'bad',
  'horrible',
]

export type QualityTier =
  | 'all'
  | 'powder'
  | 'excellent'
  | 'great'
  | 'good'
  | 'decent'
  | 'mediocre'

interface QualityFilterProps {
  selected: QualityTier
  onChange: (tier: QualityTier) => void
}

// Each tier includes that quality level and everything above it
// minIndex = index of the lowest quality level included in this tier
// qualitiesForTier slices QUALITY_SCALE[0..minIndex] inclusive
const tiers: { key: QualityTier; label: string; minIndex: number }[] = [
  { key: 'all', label: 'All', minIndex: -1 },
  { key: 'powder', label: 'Powder+', minIndex: 1 },       // champagne_powder, powder_day
  { key: 'excellent', label: 'Excellent+', minIndex: 2 },  // + excellent
  { key: 'great', label: 'Great+', minIndex: 3 },          // + great
  { key: 'good', label: 'Good+', minIndex: 4 },            // + good
  { key: 'decent', label: 'Decent+', minIndex: 5 },        // + decent
  { key: 'mediocre', label: 'Mediocre+', minIndex: 6 },    // + mediocre
]

export function qualitiesForTier(tier: QualityTier): SnowQuality[] | null {
  if (tier === 'all') return null
  const tierDef = tiers.find((t) => t.key === tier)
  if (!tierDef) return null
  // Include everything from index 0 up to and including minIndex
  return QUALITY_SCALE.slice(0, tierDef.minIndex + 1)
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
