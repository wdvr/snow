/** Convert Celsius to Fahrenheit */
export function cToF(celsius: number): number {
  return celsius * 9 / 5 + 32
}

/** Format temperature with both units */
export function formatTemp(celsius: number | null | undefined): string {
  if (celsius == null) return '--'
  return `${Math.round(celsius)}\u00B0C`
}

/** Format temperature in Fahrenheit */
export function formatTempF(celsius: number | null | undefined): string {
  if (celsius == null) return '--'
  return `${Math.round(cToF(celsius))}\u00B0F`
}

/** Format centimeters of snow */
export function formatSnowCm(cm: number | null | undefined): string {
  if (cm == null) return '--'
  return `${cm.toFixed(1)} cm`
}

/** Format centimeters as inches */
export function formatSnowInches(cm: number | null | undefined): string {
  if (cm == null) return '--'
  const inches = cm / 2.54
  return `${inches.toFixed(1)}"`
}

/** Format wind speed */
export function formatWind(kmh: number | null | undefined): string {
  if (kmh == null) return '--'
  return `${Math.round(kmh)} km/h`
}

/** Format visibility in meters/km */
export function formatVisibility(meters: number | null | undefined): string {
  if (meters == null) return '--'
  if (meters >= 10000) return '>10 km'
  if (meters >= 1000) return `${(meters / 1000).toFixed(1)} km`
  return `${Math.round(meters)} m`
}

/** Get visibility severity color class */
export function visibilitySeverity(meters: number | null | undefined): string {
  if (meters == null) return ''
  if (meters < 200) return 'text-red-600 font-medium'
  if (meters < 1000) return 'text-orange-500 font-medium'
  if (meters < 5000) return 'text-yellow-600'
  return ''
}

/** Format a quality label */
export function formatQuality(quality: string | null | undefined): string {
  if (!quality || quality === 'unknown') return 'Unknown'
  return quality.charAt(0).toUpperCase() + quality.slice(1)
}

/** Format a date string for display */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '--'
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

/** Format a timestamp for chat messages */
export function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)

    if (diffMin < 1) return 'Just now'
    if (diffMin < 60) return `${diffMin}m ago`

    const diffHrs = Math.floor(diffMin / 60)
    if (diffHrs < 24) return `${diffHrs}h ago`

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

/** Country code to flag emoji */
export function countryFlag(code: string): string {
  if (!code || code.length !== 2) return ''
  const offset = 0x1f1e6
  const a = code.toUpperCase().charCodeAt(0) - 65 + offset
  const b = code.toUpperCase().charCodeAt(1) - 65 + offset
  return String.fromCodePoint(a, b)
}

/** Region ID to display name */
export function regionDisplayName(regionId: string): string {
  const names: Record<string, string> = {
    na_west: 'NA West Coast',
    na_rockies: 'Rockies',
    na_east: 'NA East',
    alps: 'Alps',
    scandinavia: 'Scandinavia',
    japan: 'Japan',
    oceania: 'Oceania',
    south_america: 'South America',
  }
  return names[regionId] ?? regionId
}
