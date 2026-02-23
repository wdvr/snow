import type { SnowQuality } from '../api/types'

export const qualityColors: Record<SnowQuality, { bg: string; text: string; border: string; hex: string }> = {
  excellent: {
    bg: 'bg-emerald-500',
    text: 'text-emerald-500',
    border: 'border-emerald-500',
    hex: '#10b981',
  },
  good: {
    bg: 'bg-blue-500',
    text: 'text-blue-500',
    border: 'border-blue-500',
    hex: '#3b82f6',
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
