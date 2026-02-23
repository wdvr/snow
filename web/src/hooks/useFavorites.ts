import { useState, useCallback, useEffect } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/useAuth'

const STORAGE_KEY = 'pc_favorites'

function loadFavorites(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function saveFavorites(ids: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<string[]>(loadFavorites)
  const { isAuthenticated } = useAuth()

  // Sync with server on login
  useEffect(() => {
    if (isAuthenticated) {
      api
        .getMe()
        .then(() => {
          // If the user has server-side favorites, merge them
          // (for now, localStorage is the source of truth)
        })
        .catch(() => {})
    }
  }, [isAuthenticated])

  const toggleFavorite = useCallback((resortId: string) => {
    setFavorites((prev) => {
      const next = prev.includes(resortId)
        ? prev.filter((id) => id !== resortId)
        : [...prev, resortId]
      saveFavorites(next)
      return next
    })
  }, [])

  const isFavorite = useCallback(
    (resortId: string) => {
      return favorites.includes(resortId)
    },
    [favorites],
  )

  return { favorites, toggleFavorite, isFavorite }
}
