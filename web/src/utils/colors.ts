import type { SnowQuality } from '../api/types'

export const qualityColors: Record<SnowQuality, { bg: string; text: string; border: string; hex: string }> = {
  champagne_powder: {
    bg: 'bg-indigo-500',
    text: 'text-indigo-500',
    border: 'border-indigo-500',
    hex: '#6366f1',
  },
  powder_day: {
    bg: 'bg-blue-600',
    text: 'text-blue-600',
    border: 'border-blue-600',
    hex: '#2563eb',
  },
  excellent: {
    bg: 'bg-emerald-500',
    text: 'text-emerald-500',
    border: 'border-emerald-500',
    hex: '#10b981',
  },
  great: {
    bg: 'bg-green-500',
    text: 'text-green-500',
    border: 'border-green-500',
    hex: '#22c55e',
  },
  good: {
    bg: 'bg-blue-500',
    text: 'text-blue-500',
    border: 'border-blue-500',
    hex: '#3b82f6',
  },
  decent: {
    bg: 'bg-lime-500',
    text: 'text-lime-500',
    border: 'border-lime-500',
    hex: '#84cc16',
  },
  mediocre: {
    bg: 'bg-yellow-500',
    text: 'text-yellow-500',
    border: 'border-yellow-500',
    hex: '#eab308',
  },
  fair: {
    bg: 'bg-amber-500',
    text: 'text-amber-500',
    border: 'border-amber-500',
    hex: '#f59e0b',
  },
  poor: {
    bg: 'bg-orange-500',
    text: 'text-orange-500',
    border: 'border-orange-500',
    hex: '#f97316',
  },
  slushy: {
    bg: 'bg-orange-600',
    text: 'text-orange-600',
    border: 'border-orange-600',
    hex: '#ea580c',
  },
  bad: {
    bg: 'bg-red-500',
    text: 'text-red-500',
    border: 'border-red-500',
    hex: '#ef4444',
  },
  horrible: {
    bg: 'bg-red-800',
    text: 'text-red-800',
    border: 'border-red-800',
    hex: '#991b1b',
  },
  unknown: {
    bg: 'bg-gray-400',
    text: 'text-gray-400',
    border: 'border-gray-400',
    hex: '#9ca3af',
  },
}

export function getQualityColor(quality: SnowQuality | string | undefined) {
  const key = (quality?.toLowerCase() ?? 'unknown') as SnowQuality
  return qualityColors[key] ?? qualityColors.unknown
}
