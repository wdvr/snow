import { useState } from 'react'
import { Map, ExternalLink, ZoomIn, ZoomOut, X } from 'lucide-react'

interface TrailMapCardProps {
  trailMapUrl: string
  resortName: string
}

/** Returns true if the URL points directly to an image file */
function isDirectImageUrl(url: string): boolean {
  try {
    const pathname = new URL(url).pathname.toLowerCase()
    return /\.(jpg|jpeg|png|webp|gif|bmp|tiff?)$/.test(pathname)
  } catch {
    return false
  }
}

export function TrailMapCard({ trailMapUrl, resortName }: TrailMapCardProps) {
  const [imageError, setImageError] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const isImage = isDirectImageUrl(trailMapUrl)

  // For page URLs (DZI viewers like skiresort.info), show a link card
  if (!isImage || imageError) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Map className="w-4 h-4 text-blue-500" />
          Trail Map
        </h3>
        <a
          href={trailMapUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 w-full px-4 py-3 bg-blue-50 text-blue-700 font-medium rounded-lg hover:bg-blue-100 transition-colors border border-blue-200"
        >
          <Map className="w-5 h-5" />
          View Trail Map for {resortName}
          <ExternalLink className="w-4 h-4" />
        </a>
        <p className="text-xs text-gray-400 mt-2 text-center">
          Opens interactive trail map in a new tab
        </p>
      </div>
    )
  }

  // For direct image URLs, show the image inline with zoom capability
  return (
    <>
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Map className="w-4 h-4 text-blue-500" />
          Trail Map
        </h3>
        <div
          className="relative cursor-pointer group rounded-lg overflow-hidden bg-gray-50"
          onClick={() => setFullscreen(true)}
        >
          {!imageLoaded && (
            <div className="flex items-center justify-center py-16">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          <img
            src={trailMapUrl}
            alt={`Trail map for ${resortName}`}
            className={`w-full h-auto rounded-lg transition-opacity ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
          />
          {imageLoaded && (
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
              <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 rounded-full p-2 shadow-lg">
                <ZoomIn className="w-5 h-5 text-gray-700" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Fullscreen overlay */}
      {fullscreen && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          onClick={() => setFullscreen(false)}
        >
          <button
            onClick={() => setFullscreen(false)}
            className="absolute top-4 right-4 z-50 p-2 bg-white/20 hover:bg-white/30 rounded-full transition-colors"
          >
            <X className="w-6 h-6 text-white" />
          </button>
          <a
            href={trailMapUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="absolute top-4 left-4 z-50 flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-white text-sm transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
            Open full size
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
          <img
            src={trailMapUrl}
            alt={`Trail map for ${resortName}`}
            className="max-w-[95vw] max-h-[95vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}
