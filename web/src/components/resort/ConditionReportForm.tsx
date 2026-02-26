import { useState } from 'react'
import { X, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useAuth } from '../../auth/useAuth'
import type { ConditionType, ElevationLevel } from '../../api/types'

interface ConditionReportFormProps {
  resortId: string
  onClose: () => void
}

const CONDITION_TYPES: { value: ConditionType; label: string }[] = [
  { value: 'powder', label: 'Powder' },
  { value: 'packed_powder', label: 'Packed Powder' },
  { value: 'soft', label: 'Soft' },
  { value: 'hardpack', label: 'Hardpack' },
  { value: 'ice', label: 'Ice' },
  { value: 'crud', label: 'Crud' },
  { value: 'spring', label: 'Spring' },
  { value: 'windblown', label: 'Windblown' },
]

const ELEVATION_LEVELS: { value: ElevationLevel | ''; label: string }[] = [
  { value: '', label: 'Not specified' },
  { value: 'base', label: 'Base' },
  { value: 'mid', label: 'Mid-Mountain' },
  { value: 'top', label: 'Summit' },
]

export function ConditionReportForm({ resortId, onClose }: ConditionReportFormProps) {
  const { isAuthenticated, loginAsGuest } = useAuth()
  const queryClient = useQueryClient()

  const [conditionType, setConditionType] = useState<ConditionType>('powder')
  const [score, setScore] = useState(7)
  const [elevationLevel, setElevationLevel] = useState<string>('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)

    try {
      // Auto-authenticate as guest if not logged in
      if (!isAuthenticated) {
        await loginAsGuest()
      }

      await api.submitConditionReport(resortId, {
        condition_type: conditionType,
        score,
        elevation_level: elevationLevel || undefined,
        comment: comment.trim() || undefined,
      })

      setSuccess(true)
      // Refresh the reports list
      queryClient.invalidateQueries({ queryKey: ['condition-reports', resortId] })

      // Close after a brief delay
      setTimeout(() => {
        onClose()
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit report')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Submit Condition Report</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {success ? (
          <div className="p-8 text-center">
            <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
            <p className="text-lg font-medium text-gray-900">Report Submitted!</p>
            <p className="text-sm text-gray-500 mt-1">Thanks for sharing conditions.</p>
          </div>
        ) : (
          <div className="p-5 space-y-5">
            {/* Condition type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Condition Type
              </label>
              <div className="grid grid-cols-2 gap-2">
                {CONDITION_TYPES.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => setConditionType(value)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                      conditionType === value
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Score slider */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Score: <span className="text-blue-600 font-bold text-lg">{score}</span>/10
              </label>
              <input
                type="range"
                min={1}
                max={10}
                value={score}
                onChange={(e) => setScore(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-full appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>Poor</span>
                <span>Excellent</span>
              </div>
            </div>

            {/* Elevation level */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Elevation Level <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <div className="flex gap-2">
                {ELEVATION_LEVELS.map(({ value, label }) => (
                  <button
                    key={value || 'none'}
                    onClick={() => setElevationLevel(value)}
                    className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                      elevationLevel === value
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Comment */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Comment <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="How were conditions today?"
                maxLength={500}
                rows={3}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
              <p className="text-xs text-gray-400 mt-1 text-right">
                {comment.length}/500
              </p>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                'Submit Report'
              )}
            </button>

            {!isAuthenticated && (
              <p className="text-xs text-gray-400 text-center">
                You will be signed in as a guest automatically.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
