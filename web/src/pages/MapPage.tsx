import { useState, useMemo, useCallback, useRef } from 'react'
import { Loader2, Layers } from 'lucide-react'
import L from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import 'leaflet/dist/leaflet.css'

import { useResorts, useSnowQualityBatch, useNearbyResorts } from '../hooks/useResorts'
import { useGeolocation } from '../hooks/useGeolocation'
import { getQualityColor } from '../utils/colors'
import type { Resort, SnowQualitySummary, SnowQuality, ElevationPoint } from '../api/types'

import { QualityFilter, qualitiesForTier, type QualityTier } from '../components/map/QualityFilter'
import {
  RegionPresets,
  type RegionPreset,
} from '../components/map/RegionPresets'
import { ResortPopup } from '../components/map/ResortPopup'
import { NearbyCarousel } from '../components/map/NearbyCarousel'

// --- Helpers ---

function getResortCoords(resort: Resort): { lat: number; lon: number } | null {
  const mid = resort.elevation_points?.find((e: ElevationPoint) => e.level === 'mid')
  const top = resort.elevation_points?.find((e: ElevationPoint) => e.level === 'top')
  const base = resort.elevation_points?.find((e: ElevationPoint) => e.level === 'base')
  const point = mid ?? top ?? base
  if (!point || !point.latitude || !point.longitude) return null
  return { lat: point.latitude, lon: point.longitude }
}

// Custom cluster icon creator with quality-colored clusters
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function createClusterCustomIcon(cluster: any) {
  const count = cluster.getChildCount()
  let size = 'w-8 h-8 text-xs'
  if (count >= 50) size = 'w-12 h-12 text-sm'
  else if (count >= 20) size = 'w-10 h-10 text-sm'

  return L.divIcon({
    html: `<div class="flex items-center justify-center ${size} rounded-full bg-blue-600 text-white font-bold shadow-lg border-2 border-white">${count}</div>`,
    className: 'custom-cluster-icon',
    iconSize: L.point(40, 40, true),
  })
}

// --- Map controller for imperative operations ---

function MapController({
  flyTo,
}: {
  flyTo: { center: [number, number]; zoom: number } | null
}) {
  const map = useMap()
  const lastFlyTo = useRef<string | null>(null)

  if (flyTo) {
    const key = `${flyTo.center[0]},${flyTo.center[1]},${flyTo.zoom}`
    if (lastFlyTo.current !== key) {
      lastFlyTo.current = key
      map.flyTo(flyTo.center, flyTo.zoom, { duration: 1 })
    }
  }

  return null
}

// --- Tile layers ---

const TILE_LAYERS = {
  standard: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
  },
  terrain: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
  },
}

type TileLayerKey = keyof typeof TILE_LAYERS

// --- Main Page ---

export function MapPage() {
  const [qualityTier, setQualityTier] = useState<QualityTier>('all')
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [tileLayer, setTileLayer] = useState<TileLayerKey>('standard')
  const [flyTo, setFlyTo] = useState<{ center: [number, number]; zoom: number } | null>(null)

  const geo = useGeolocation()
  const { data: resorts, isLoading: resortsLoading } = useResorts()
  const { data: nearbyData } = useNearbyResorts(geo.latitude, geo.longitude)

  // Batch quality for all resorts
  const resortIds = useMemo(() => resorts?.map((r) => r.resort_id) ?? [], [resorts])
  const { data: qualityMap } = useSnowQualityBatch(resortIds)

  // Allowed qualities for the selected tier
  const allowedQualities = useMemo(() => qualitiesForTier(qualityTier), [qualityTier])

  // Filter resorts by quality tier and compute coords
  const markers = useMemo(() => {
    if (!resorts) return []

    return resorts
      .map((resort) => {
        const coords = getResortCoords(resort)
        if (!coords) return null
        const quality = qualityMap?.[resort.resort_id]

        // Filter by quality tier
        if (allowedQualities) {
          const q = quality?.overall_quality ?? 'unknown'
          if (!allowedQualities.includes(q as SnowQuality)) return null
        }

        return { resort, coords, quality }
      })
      .filter(Boolean) as { resort: Resort; coords: { lat: number; lon: number }; quality?: SnowQualitySummary }[]
  }, [resorts, qualityMap, allowedQualities])

  const handleRegionSelect = useCallback((preset: RegionPreset) => {
    setSelectedRegion((prev) => (prev === preset.key ? null : preset.key))
    const center = preset.center as [number, number]
    setFlyTo({ center, zoom: preset.zoom })
  }, [])

  const handleLocateResort = useCallback((lat: number, lon: number) => {
    setFlyTo({ center: [lat, lon], zoom: 12 })
  }, [])

  const cycleTileLayer = useCallback(() => {
    setTileLayer((prev) => {
      const keys = Object.keys(TILE_LAYERS) as TileLayerKey[]
      const idx = keys.indexOf(prev)
      return keys[(idx + 1) % keys.length]
    })
  }, [])

  const isLoading = resortsLoading

  const tile = TILE_LAYERS[tileLayer]

  return (
    <div className="relative flex flex-col" style={{ height: 'calc(100vh - 4rem)' }}>
      {/* Top controls overlay */}
      <div className="absolute top-0 left-0 right-0 z-[1000] pointer-events-none">
        <div className="p-3 space-y-2">
          {/* Region presets row */}
          <div className="pointer-events-auto">
            <RegionPresets selected={selectedRegion} onSelect={handleRegionSelect} />
          </div>

          {/* Quality filter row */}
          <div className="pointer-events-auto">
            <QualityFilter selected={qualityTier} onChange={setQualityTier} />
          </div>

          {/* Nearby carousel */}
          <div className="pointer-events-auto">
            <NearbyCarousel
              nearbyResorts={nearbyData?.resorts ?? []}
              qualityMap={qualityMap}
              onLocateResort={handleLocateResort}
              requested={geo.requested}
              requestLocation={geo.requestLocation}
            />
          </div>
        </div>
      </div>

      {/* Tile layer toggle button */}
      <div className="absolute bottom-6 right-3 z-[1000]">
        <button
          onClick={cycleTileLayer}
          className="flex items-center gap-1.5 px-3 py-2 bg-white rounded-lg shadow-md border border-gray-200 hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700"
          title={`Switch map style (current: ${tileLayer})`}
        >
          <Layers className="w-4 h-4" />
          <span className="hidden sm:inline capitalize">{tileLayer}</span>
        </button>
      </div>

      {/* Resort count badge */}
      <div className="absolute bottom-6 left-3 z-[1000]">
        <div className="px-3 py-1.5 bg-white/90 backdrop-blur-sm rounded-lg shadow-sm border border-gray-200 text-xs text-gray-600">
          {isLoading ? 'Loading...' : `${markers.length} resorts`}
        </div>
      </div>

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 z-[1001] flex items-center justify-center bg-gray-50/80">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <p className="text-sm text-gray-600 font-medium">Loading resort data...</p>
          </div>
        </div>
      )}

      {/* Map */}
      <MapContainer
        center={[42, -10]}
        zoom={3}
        className="flex-1 w-full"
        zoomControl={false}
        attributionControl={true}
      >
        <TileLayer url={tile.url} attribution={tile.attribution} />
        <MapController flyTo={flyTo} />

        <MarkerClusterGroup
          chunkedLoading
          maxClusterRadius={50}
          spiderfyOnMaxZoom
          showCoverageOnHover={false}
          iconCreateFunction={createClusterCustomIcon}
        >
          {markers.map(({ resort, coords, quality }) => {
            const color = getQualityColor(quality?.overall_quality)
            return (
              <CircleMarker
                key={resort.resort_id}
                center={[coords.lat, coords.lon]}
                radius={8}
                pathOptions={{
                  fillColor: color.hex,
                  fillOpacity: 0.9,
                  color: '#fff',
                  weight: 2,
                  opacity: 1,
                }}
              >
                <Popup closeButton={false} maxWidth={280} minWidth={200}>
                  <ResortPopup resort={resort} quality={quality} />
                </Popup>
              </CircleMarker>
            )
          })}
        </MarkerClusterGroup>
      </MapContainer>
    </div>
  )
}
