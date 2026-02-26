import { useState } from 'react'
import { X, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/useAuth'

interface SuggestEditModalProps {
  resortId: string
  resortName: string
  onClose: () => void
}

const SECTION_OPTIONS = [
  'Elevation data',
  'Lift count / trail count',
  'Location / region',
  'Pass info (Epic/Ikon)',
  'Website / webcam URL',
  'Trail map',
  'Other',
]

export function SuggestEditModal({ resortId, resortName, onClose }: SuggestEditModalProps) {
  const { isAuthenticated, loginAsGuest } = useAuth()

  const [section, setSection] = useState('')
  const [suggestion, setSuggestion] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const canSubmit = section.trim().length > 0 && suggestion.trim().length > 0

  const handleSubmit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)

    try {
      if (!isAuthenticated) {
        await loginAsGuest()
      }

      await api.submitFeedback({
        subject: `Resort Edit: ${resortName} - ${section}`,
        message: `[Resort Edit Suggestion]\nResort: ${resortName} (${resortId})\nSection: ${section}\n\nSuggested correction:\n${suggestion.trim()}`,
        app_version: 'web-1.0',
        build_number: '1',
      })

      setSuccess(true)
      setTimeout(() => {
        onClose()
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit suggestion')
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
          <h2 className="text-lg font-semibold text-gray-900">Suggest an Edit</h2>
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
            <p className="text-lg font-medium text-gray-900">Suggestion Submitted!</p>
            <p className="text-sm text-gray-500 mt-1">Thanks for helping us improve.</p>
          </div>
        ) : (
          <div className="p-5 space-y-5">
            {/* Resort name (read-only) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Resort
              </label>
              <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700">
                {resortName}
              </div>
            </div>

            {/* Section */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                What would you like to change?
              </label>
              <div className="flex flex-wrap gap-2">
                {SECTION_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setSection(opt)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                      section === opt
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            {/* Suggestion */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Your suggestion
              </label>
              <textarea
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                placeholder="Describe the correct information..."
                maxLength={1000}
                rows={4}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
              <p className="text-xs text-gray-400 mt-1 text-right">
                {suggestion.length}/1000
              </p>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 px-4 py-3 rounded-lg border border-gray-200 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !canSubmit}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  'Submit'
                )}
              </button>
            </div>

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
