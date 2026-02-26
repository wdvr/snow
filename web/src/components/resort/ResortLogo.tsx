import { useState } from 'react'

interface ResortLogoProps {
  name: string
  officialWebsite?: string | null
  logoUrl?: string | null
  size?: number
  className?: string
}

function getInitials(name: string): string {
  const skip = new Set(['ski', 'resort', 'mountain', 'area'])
  const words = name.split(' ').filter((w) => !skip.has(w.toLowerCase()))
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
}

function getLogoUrl(website: string): string | null {
  try {
    const url = new URL(website)
    return `https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://${url.hostname}&size=128`
  } catch {
    return null
  }
}

export function ResortLogo({ name, officialWebsite, logoUrl: serverLogoUrl, size = 40, className = '' }: ResortLogoProps) {
  const [imgError, setImgError] = useState(false)
  const logoUrl = serverLogoUrl || (officialWebsite ? getLogoUrl(officialWebsite) : null)

  const initials = getInitials(name)
  const fallback = (
    <div
      className={`flex items-center justify-center rounded-lg bg-gradient-to-br from-blue-400 to-cyan-400 text-white font-bold ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.35 }}
    >
      {initials}
    </div>
  )

  if (!logoUrl || imgError) {
    return fallback
  }

  return (
    <img
      src={logoUrl}
      alt={`${name} logo`}
      width={size}
      height={size}
      className={`rounded-lg object-contain ${className}`}
      onError={() => setImgError(true)}
    />
  )
}
