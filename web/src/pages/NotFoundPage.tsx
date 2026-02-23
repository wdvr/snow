import { Link } from 'react-router-dom'
import { Mountain } from 'lucide-react'

export function NotFoundPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-32 text-center">
      <Mountain className="w-16 h-16 text-gray-300 mx-auto mb-6" />
      <h1 className="text-4xl font-bold text-gray-900 mb-3">404</h1>
      <p className="text-lg text-gray-500 mb-8">
        This slope doesn't exist. Looks like you've gone off-piste.
      </p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors"
      >
        Back to the Lodge
      </Link>
    </div>
  )
}
