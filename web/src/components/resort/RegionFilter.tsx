import type { Region } from '../../api/types'

interface RegionFilterProps {
  regions: Region[]
  selected: string | null
  onChange: (regionId: string | null) => void
}

export function RegionFilter({ regions, selected, onChange }: RegionFilterProps) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
      <button
        onClick={() => onChange(null)}
        className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
          selected === null
            ? 'bg-blue-600 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
        }`}
      >
        All Regions
      </button>
      {regions.map((region) => (
        <button
          key={region.id}
          onClick={() => onChange(region.id)}
          className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
            selected === region.id
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
          }`}
        >
          {region.display_name || region.name}
          <span className="ml-1.5 text-xs opacity-70">{region.resort_count}</span>
        </button>
      ))}
    </div>
  )
}
