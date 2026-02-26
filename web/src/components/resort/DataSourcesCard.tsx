import { useState } from 'react'
import { ChevronDown, ChevronUp, Check, X, Minus, Database } from 'lucide-react'
import type { SourceDetails } from '../../api/types'

interface DataSourcesCardProps {
  sourceDetails: SourceDetails
  confidence?: string | null
  dataSource?: string
}

const MERGE_METHOD_LABELS: Record<string, string> = {
  consensus: 'Consensus',
  weighted_average: 'Weighted Average',
  single_source: 'Single Source',
  outlier_detection: 'Outlier Detection',
  median: 'Median',
}

function formatSourceName(name: string): string {
  // "open-meteo.com" -> "Open-Meteo"
  // "weatherkit.apple.com" -> "WeatherKit"
  // "onthesnow.com" -> "OnTheSnow"
  // "snow-forecast.com" -> "Snow-Forecast"
  const labels: Record<string, string> = {
    'open-meteo.com': 'Open-Meteo',
    'weatherkit.apple.com': 'WeatherKit',
    'onthesnow.com': 'OnTheSnow',
    'snow-forecast.com': 'Snow-Forecast',
  }
  return labels[name] ?? name
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'included' || status === 'consensus') {
    return <Check className="w-4 h-4 text-green-500" />
  }
  if (status === 'outlier') {
    return <X className="w-4 h-4 text-red-500" />
  }
  // no_data or other
  return <Minus className="w-4 h-4 text-gray-400" />
}

function ConfidenceBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    high: 'bg-green-100 text-green-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[level] ?? 'bg-gray-100 text-gray-600'}`}>
      {level.charAt(0).toUpperCase() + level.slice(1)} confidence
    </span>
  )
}

export function DataSourcesCard({ sourceDetails, confidence, dataSource }: DataSourcesCardProps) {
  const [isOpen, setIsOpen] = useState(false)

  const sources = Object.entries(sourceDetails.sources)
  const activeSources = sources.filter(([, detail]) => detail.status !== 'no_data')
  const mergeLabel = MERGE_METHOD_LABELS[sourceDetails.merge_method] ?? sourceDetails.merge_method

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">
            Data Sources
          </span>
          <span className="text-xs text-gray-500">
            {activeSources.length} source{activeSources.length !== 1 ? 's' : ''}
            {' '}&middot;{' '}
            {mergeLabel}
          </span>
          {confidence && <ConfidenceBadge level={confidence} />}
        </div>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {isOpen && (
        <div className="px-4 pb-4 space-y-3">
          {/* Summary row */}
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>Method: <strong className="text-gray-700">{mergeLabel}</strong></span>
            {sourceDetails.consensus_value_cm != null && (
              <span>
                Consensus: <strong className="text-gray-700">{sourceDetails.consensus_value_cm.toFixed(1)} cm</strong> (24h)
              </span>
            )}
          </div>

          {/* Per-source details */}
          <div className="space-y-2">
            {sources.map(([name, detail]) => (
              <div
                key={name}
                className={`flex items-start gap-3 p-2.5 rounded-lg bg-white border ${
                  detail.status === 'outlier'
                    ? 'border-red-200'
                    : detail.status === 'no_data'
                      ? 'border-gray-100'
                      : 'border-green-100'
                }`}
              >
                <StatusIcon status={detail.status} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{formatSourceName(name)}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      detail.status === 'included' || detail.status === 'consensus'
                        ? 'bg-green-50 text-green-700'
                        : detail.status === 'outlier'
                          ? 'bg-red-50 text-red-700'
                          : 'bg-gray-100 text-gray-500'
                    }`}>
                      {detail.status === 'no_data' ? 'No Data' : detail.status.charAt(0).toUpperCase() + detail.status.slice(1)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    {detail.snowfall_24h_cm != null ? (
                      <span className="text-xs text-gray-600">
                        24h: <strong>{detail.snowfall_24h_cm.toFixed(1)} cm</strong>
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">No snowfall data</span>
                    )}
                  </div>
                  {detail.reason && (
                    <p className="text-xs text-gray-400 mt-0.5">{detail.reason}</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Raw data source string */}
          {dataSource && (
            <p className="text-xs text-gray-400 pt-1 border-t border-gray-200">
              Combined: {dataSource}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
