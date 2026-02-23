import { useState, useCallback } from 'react'

interface GeoState {
  latitude: number | null
  longitude: number | null
  error: string | null
  loading: boolean
  requested: boolean
}

const STORAGE_KEY = 'pc_location'

export function useGeolocation() {
  const [state, setState] = useState<GeoState>(() => {
    // Check localStorage for previously granted location
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        const { latitude, longitude } = JSON.parse(stored)
        return { latitude, longitude, error: null, loading: false, requested: true }
      } catch {
        /* ignore */
      }
    }
    return { latitude: null, longitude: null, error: null, loading: false, requested: false }
  })

  const requestLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setState((prev) => ({ ...prev, error: 'Geolocation not supported', requested: true }))
      return
    }
    setState((prev) => ({ ...prev, loading: true, requested: true }))
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ latitude, longitude }))
        setState({ latitude, longitude, error: null, loading: false, requested: true })
      },
      (err) => {
        setState((prev) => ({ ...prev, error: err.message, loading: false, requested: true }))
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    )
  }, [])

  return { ...state, requestLocation }
}
