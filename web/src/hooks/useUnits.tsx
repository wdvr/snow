import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { cToF } from '../utils/format'

export type TempUnit = 'celsius' | 'fahrenheit'
export type SnowUnit = 'cm' | 'inches'

interface UnitPreferences {
  tempUnit: TempUnit
  snowUnit: SnowUnit
}

interface UnitContextValue extends UnitPreferences {
  setTempUnit: (unit: TempUnit) => void
  setSnowUnit: (unit: SnowUnit) => void
  formatTemp: (celsius: number | null | undefined) => string
  formatSnow: (cm: number | null | undefined) => string
  formatSnowInt: (cm: number | null | undefined) => string
  tempLabel: string
  snowLabel: string
}

const STORAGE_KEY = 'pc_unit_preferences'

function loadPreferences(): UnitPreferences {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      return {
        tempUnit: parsed.tempUnit === 'fahrenheit' ? 'fahrenheit' : 'celsius',
        snowUnit: parsed.snowUnit === 'inches' ? 'inches' : 'cm',
      }
    }
  } catch {
    /* ignore */
  }
  return { tempUnit: 'celsius', snowUnit: 'cm' }
}

function savePreferences(prefs: UnitPreferences) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
}

const UnitContext = createContext<UnitContextValue | null>(null)

export function UnitProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<UnitPreferences>(loadPreferences)

  const setTempUnit = useCallback((unit: TempUnit) => {
    setPrefs((prev) => {
      const next = { ...prev, tempUnit: unit }
      savePreferences(next)
      return next
    })
  }, [])

  const setSnowUnit = useCallback((unit: SnowUnit) => {
    setPrefs((prev) => {
      const next = { ...prev, snowUnit: unit }
      savePreferences(next)
      return next
    })
  }, [])

  const formatTemp = useCallback(
    (celsius: number | null | undefined): string => {
      if (celsius == null) return '--'
      if (prefs.tempUnit === 'fahrenheit') {
        return `${Math.round(cToF(celsius))}\u00B0F`
      }
      return `${Math.round(celsius)}\u00B0C`
    },
    [prefs.tempUnit],
  )

  const formatSnow = useCallback(
    (cm: number | null | undefined): string => {
      if (cm == null) return '--'
      if (prefs.snowUnit === 'inches') {
        const inches = cm / 2.54
        return `${inches.toFixed(1)}"`
      }
      return `${cm.toFixed(1)} cm`
    },
    [prefs.snowUnit],
  )

  const formatSnowInt = useCallback(
    (cm: number | null | undefined): string => {
      if (cm == null) return '--'
      if (prefs.snowUnit === 'inches') {
        const inches = cm / 2.54
        return `${Math.round(inches)}"`
      }
      return `${Math.round(cm)} cm`
    },
    [prefs.snowUnit],
  )

  const tempLabel = prefs.tempUnit === 'fahrenheit' ? '\u00B0F' : '\u00B0C'
  const snowLabel = prefs.snowUnit === 'inches' ? '"' : 'cm'

  const value = useMemo<UnitContextValue>(
    () => ({
      ...prefs,
      setTempUnit,
      setSnowUnit,
      formatTemp,
      formatSnow,
      formatSnowInt,
      tempLabel,
      snowLabel,
    }),
    [prefs, setTempUnit, setSnowUnit, formatTemp, formatSnow, formatSnowInt, tempLabel, snowLabel],
  )

  return <UnitContext.Provider value={value}>{children}</UnitContext.Provider>
}

export function useUnits() {
  const context = useContext(UnitContext)
  if (!context) {
    throw new Error('useUnits must be used within a UnitProvider')
  }
  return context
}
