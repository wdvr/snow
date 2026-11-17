import { CalendarClock, CalendarX, Moon, CirclePause, Snowflake } from 'lucide-react'
import type { SnowQuality } from '../../api/types'
import { formatQuality } from '../../utils/format'
import { seasonCountdown, seasonTitle, type SeasonDisplay } from '../../utils/season'

function SeasonIcon({ display, className }: { display: SeasonDisplay; className?: string }) {
  switch (display.kind) {
    case 'opensOn':
    case 'notOpenYet':
      return <CalendarClock className={className} />
    case 'closesOn':
      return <CalendarX className={className} />
    case 'closedForSeason':
      return <Moon className={className} />
    case 'temporarilyClosed':
      return <CirclePause className={className} />
  }
}

/** Dominant season status for a resort that isn't open: "Opens Dec 4" with a
 * countdown when near, or "Closed for season". */
export function SeasonBadge({ display, large = false }: { display: SeasonDisplay; large?: boolean }) {
  const countdown = seasonCountdown(display)
  return (
    <div
      className={`inline-flex flex-col items-end rounded-lg bg-gray-100 text-gray-900 ${
        large ? 'px-3 py-2' : 'px-2 py-1'
      }`}
      data-testid="season-badge"
    >
      <span className={`flex items-center gap-1 font-semibold whitespace-nowrap ${large ? 'text-base' : 'text-xs'}`}>
        <SeasonIcon display={display} className={large ? 'w-4 h-4' : 'w-3.5 h-3.5'} />
        {seasonTitle(display)}
      </span>
      {countdown && (
        <span className={`text-gray-500 ${large ? 'text-sm' : 'text-[11px] leading-tight'}`}>{countdown}</span>
      )}
    </div>
  )
}

/** Small inline note for open resorts nearing their closing date. */
export function SeasonNote({ display }: { display: SeasonDisplay }) {
  const countdown = seasonCountdown(display)
  return (
    <div className="flex items-center gap-1 text-xs text-orange-600" data-testid="season-note">
      <SeasonIcon display={display} className="w-3.5 h-3.5 shrink-0" />
      <span>{seasonTitle(display)}</span>
      {countdown && <span>· {countdown}</span>}
    </div>
  )
}

/** Muted snow score for closed resorts ("❄ 74 Great"). */
export function SecondaryScoreLabel({ quality, score }: { quality: SnowQuality | string; score?: number | null }) {
  return (
    <span
      className="flex items-center gap-1 text-[11px] text-gray-400"
      aria-label={`Snow forecast: ${formatQuality(quality)}${score != null ? `, score ${score}` : ''}`}
      data-testid="secondary-score"
    >
      <Snowflake className="w-3 h-3" />
      {score != null && <span>{score}</span>}
      <span>{formatQuality(quality)}</span>
    </span>
  )
}
