import { Link } from 'react-router-dom'
import { MapPin, Navigation } from 'lucide-react'
import type { Resort, SnowQualitySummary } from '../../api/types'
import { QualityBadge } from '../resort/QualityBadge'
import { countryFlag } from '../../utils/format'

interface NearbyCarouselProps {
  nearbyResorts: { resort: Resort; distance_km: number }[]
  qualityMap: Record<string, SnowQualitySummary> | undefined
  onLocateResort: (lat: number, lon: number) => void
  requested: boolean
  requestLocation: () => void
}

export function NearbyCarousel({
  nearbyResorts,
  qualityMap,
  onLocateResort,
  requested,
  requestLocation,
}: NearbyCarouselProps) {
  if (!requested) {
    return (
      <button
        onClick={requestLocation}
        className="flex items-center gap-2 px-3 py-2 bg-white/90 backdrop-blur-sm rounded-lg border border-gray-200 hover:bg-white transition-colors text-sm shadow-sm"
      >
        <Navigation className="w-4 h-4 text-blue-600" />
        <span className="text-gray-700 font-medium">Near You</span>
      </button>
    )
  }

  if (!nearbyResorts || nearbyResorts.length === 0) return null

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      <div className="flex items-center gap-1 text-blue-600 shrink-0">
        <MapPin className="w-4 h-4" />
      </div>
      {nearbyResorts.slice(0, 6).map(({ resort, distance_km }) => {
        const mid = resort.elevation_points?.find((e) => e.level === 'mid')
        const top = resort.elevation_points?.find((e) => e.level === 'top')
        const base = resort.elevation_points?.find((e) => e.level === 'base')
        const point = mid ?? top ?? base

        return (
          <button
            key={resort.resort_id}
            onClick={() => {
              if (point) onLocateResort(point.latitude, point.longitude)
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-white/90 backdrop-blur-sm rounded-lg border border-gray-200 hover:bg-white transition-colors shrink-0 shadow-sm"
          >
            <div className="min-w-0">
              <p className="text-xs font-medium text-gray-900 truncate max-w-[120px]">
                {countryFlag(resort.country)} {resort.name}
              </p>
              <p className="text-[10px] text-gray-500">{Math.round(distance_km)} km</p>
            </div>
            <QualityBadge
              quality={qualityMap?.[resort.resort_id]?.overall_quality}
              score={qualityMap?.[resort.resort_id]?.snow_score}
              size="sm"
            />
          </button>
        )
      })}
      <Link
        to="/"
        className="text-xs text-blue-600 hover:underline whitespace-nowrap shrink-0 px-2"
      >
        See all
      </Link>
    </div>
  )
}
