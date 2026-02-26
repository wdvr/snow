import type { LatLngExpression } from 'leaflet'

export interface RegionPreset {
  key: string
  label: string
  center: LatLngExpression
  zoom: number
}

export const regionPresets: RegionPreset[] = [
  { key: 'world', label: 'World', center: [35, 0], zoom: 2 },
  { key: 'na_west', label: 'NA West', center: [45.5, -121.5], zoom: 5 },
  { key: 'na_rockies', label: 'Rockies', center: [40.5, -106.5], zoom: 6 },
  { key: 'na_east', label: 'NA East', center: [44.5, -71.5], zoom: 6 },
  { key: 'alps', label: 'Alps', center: [46.8, 10.0], zoom: 6 },
  { key: 'scandinavia', label: 'Scandinavia', center: [62.0, 14.0], zoom: 5 },
  { key: 'japan', label: 'Japan', center: [37.0, 138.5], zoom: 7 },
  { key: 'oceania', label: 'Oceania', center: [-38.0, 148.0], zoom: 5 },
  { key: 'south_america', label: 'S. America', center: [-33.0, -70.0], zoom: 6 },
]

interface RegionPresetsProps {
  selected: string | null
  onSelect: (preset: RegionPreset) => void
}

export function RegionPresets({ selected, onSelect }: RegionPresetsProps) {
  return (
    <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
      {regionPresets.map((preset) => (
        <button
          key={preset.key}
          onClick={() => onSelect(preset)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
            selected === preset.key
              ? 'bg-slate-700 text-white shadow-sm'
              : 'bg-white/90 text-gray-700 hover:bg-white border border-gray-200'
          }`}
        >
          {preset.label}
        </button>
      ))}
    </div>
  )
}
