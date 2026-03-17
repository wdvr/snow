import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2, Layers, Mountain } from 'lucide-react'
import L from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap, useMapEvents } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import 'leaflet/dist/leaflet.css'

import { useResorts, flattenResorts, useSnowQualityBatch, useNearbyResorts } from '../hooks/useResorts'
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

// Quality color grouping for cluster pie chart (matches iOS: green/yellow/orange/red/black)
const CLUSTER_COLOR_GROUPS: { color: string; qualities: string[] }[] = [
  { color: '#22c55e', qualities: ['#6366f1', '#2563eb', '#10b981', '#22c55e', '#3b82f6'] }, // green: champagne, powder, excellent, great, good
  { color: '#eab308', qualities: ['#84cc16', '#eab308', '#f59e0b'] }, // yellow: decent, mediocre, fair
  { color: '#f97316', qualities: ['#f97316', '#ea580c'] }, // orange: poor, slushy
  { color: '#ef4444', qualities: ['#ef4444'] }, // red: bad
  { color: '#1a1a1a', qualities: ['#991b1b'] }, // black: horrible
]

function getClusterGroup(hex: string): string {
  for (const group of CLUSTER_COLOR_GROUPS) {
    if (group.qualities.includes(hex)) return group.color
  }
  return '#9ca3af' // gray for unknown
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function createClusterCustomIcon(cluster: any) {
  const count = cluster.getChildCount()
  const childMarkers = cluster.getAllChildMarkers()

  // Count resorts per color group
  const groupCounts: Record<string, number> = {}
  for (const marker of childMarkers) {
    const fillColor = marker.options?.fillColor || marker.options?.pathOptions?.fillColor || '#9ca3af'
    const group = getClusterGroup(fillColor)
    groupCounts[group] = (groupCounts[group] || 0) + 1
  }

  // Determine size based on count
  let diameter = 36
  if (count >= 50) diameter = 48
  else if (count >= 20) diameter = 42

  const radius = diameter / 2
  const center = radius

  // Build SVG pie chart
  const segments = Object.entries(groupCounts).filter(([, c]) => c > 0)
  const total = segments.reduce((sum, [, c]) => sum + c, 0)

  let svg: string
  if (segments.length === 1) {
    // Single color — just fill the circle
    svg = `<circle cx="${center}" cy="${center}" r="${radius - 2}" fill="${segments[0][0]}" />`
  } else {
    // Pie chart segments
    let startAngle = -Math.PI / 2
    const paths: string[] = []
    for (const [color, segCount] of segments) {
      const angle = (segCount / total) * 2 * Math.PI
      const endAngle = startAngle + angle
      const x1 = center + (radius - 2) * Math.cos(startAngle)
      const y1 = center + (radius - 2) * Math.sin(startAngle)
      const x2 = center + (radius - 2) * Math.cos(endAngle)
      const y2 = center + (radius - 2) * Math.sin(endAngle)
      const largeArc = angle > Math.PI ? 1 : 0
      paths.push(
        `<path d="M${center},${center} L${x1},${y1} A${radius - 2},${radius - 2} 0 ${largeArc} 1 ${x2},${y2} Z" fill="${color}" />`
      )
      startAngle = endAngle
    }
    svg = paths.join('')
  }

  const countDisplay = count > 99 ? '99+' : count
  const fontSize = count >= 50 ? 12 : count >= 20 ? 11 : 10

  const html = `
    <svg width="${diameter}" height="${diameter}" viewBox="0 0 ${diameter} ${diameter}" xmlns="http://www.w3.org/2000/svg">
      ${svg}
      <circle cx="${center}" cy="${center}" r="${radius - 2}" fill="none" stroke="white" stroke-width="2.5" />
      <circle cx="${center}" cy="${center}" r="${radius * 0.55}" fill="white" fill-opacity="0.9" />
      <text x="${center}" y="${center}" text-anchor="middle" dominant-baseline="central"
        font-size="${fontSize}" font-weight="700" fill="#1f2937">${countDisplay}</text>
    </svg>`

  return L.divIcon({
    html,
    className: 'custom-cluster-icon',
    iconSize: L.point(diameter, diameter, true),
    iconAnchor: L.point(center, center, true),
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

// --- Piste overlay (OpenSnowMap) ---

const PISTE_OVERLAY = {
  url: 'https://tiles.opensnowmap.org/pistes/{z}/{x}/{y}.png',
  attribution: '&copy; <a href="https://www.opensnowmap.org">OpenSnowMap</a> / <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  minZoom: 12,
}

// Component that shows/hides piste overlay based on zoom level and toggle
function PisteOverlay({ enabled }: { enabled: boolean }) {
  const [zoom, setZoom] = useState(3)

  useMapEvents({
    zoomend: (e) => {
      setZoom(e.target.getZoom())
    },
  })

  if (!enabled || zoom < PISTE_OVERLAY.minZoom) return null

  return (
    <TileLayer
      url={PISTE_OVERLAY.url}
      attribution={PISTE_OVERLAY.attribution}
      minZoom={PISTE_OVERLAY.minZoom}
      maxZoom={18}
      opacity={0.85}
    />
  )
}

// --- Main Page ---

export function MapPage() {
  const [searchParams] = useSearchParams()
  const [qualityTier, setQualityTier] = useState<QualityTier>('all')
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [tileLayer, setTileLayer] = useState<TileLayerKey>('standard')
  const [showPistes, setShowPistes] = useState(false)
  const [flyTo, setFlyTo] = useState<{ center: [number, number]; zoom: number } | null>(null)

  // Fly to resort location from URL query params (e.g. ?lat=46.8&lon=6.9&zoom=12)
  const hasAppliedUrlParams = useRef(false)
  useEffect(() => {
    if (hasAppliedUrlParams.current) return
    const lat = parseFloat(searchParams.get('lat') ?? '')
    const lon = parseFloat(searchParams.get('lon') ?? '')
    const zoom = parseInt(searchParams.get('zoom') ?? '12', 10)
    if (!isNaN(lat) && !isNaN(lon)) {
      hasAppliedUrlParams.current = true
      setFlyTo({ center: [lat, lon], zoom })
    }
  }, [searchParams])

  const geo = useGeolocation()
  const {
    data: resortsData,
    isLoading: resortsLoading,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useResorts()
  const resorts = useMemo(() => flattenResorts(resortsData), [resortsData])
  const { data: nearbyData } = useNearbyResorts(geo.latitude, geo.longitude)

  // Auto-load all pages for the map (we need all markers)
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage()
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  // Batch quality for all resorts
  const resortIds = useMemo(() => resorts.map((r) => r.resort_id), [resorts])
  const { data: qualityMap } = useSnowQualityBatch(resortIds)

  // Allowed qualities for the selected tier
  const allowedQualities = useMemo(() => qualitiesForTier(qualityTier), [qualityTier])

  // Filter resorts by quality tier and compute coords
  const markers = useMemo(() => {
    if (resorts.length === 0) return []

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

      {/* Map control buttons */}
      <div className="absolute bottom-6 right-3 z-[1000] flex flex-col gap-2">
        <button
          onClick={() => setShowPistes((prev) => !prev)}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg shadow-md border transition-colors text-sm font-medium ${
            showPistes
              ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
              : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
          }`}
          title={showPistes ? 'Hide ski trails' : 'Show ski trails (zoom in to see)'}
        >
          <Mountain className="w-4 h-4" />
          <span className="hidden sm:inline">Trails</span>
        </button>
        <button
          onClick={cycleTileLayer}
          className="flex items-center gap-1.5 px-3 py-2 bg-white rounded-lg shadow-md border border-gray-200 hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700"
          title={`Switch map style (current: ${tileLayer})`}
        >
          <Layers className="w-4 h-4" />
          <span className="hidden sm:inline capitalize">{tileLayer}</span>
        </button>
      </div>

      {/* Resort count badge + piste attribution */}
      <div className="absolute bottom-6 left-3 z-[1000] flex flex-col gap-1.5">
        {showPistes && (
          <div className="px-3 py-1.5 bg-white/90 backdrop-blur-sm rounded-lg shadow-sm border border-gray-200 text-xs text-gray-500">
            Ski trails: <a href="https://www.opensnowmap.org" target="_blank" rel="noopener noreferrer" className="underline">OpenSnowMap</a> / OSM &middot; Zoom in to see trails
          </div>
        )}
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
        <PisteOverlay enabled={showPistes} />
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
                fillColor={color.hex}
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
