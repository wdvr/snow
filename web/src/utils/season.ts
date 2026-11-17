import type { Resort, SeasonStatus } from '../api/types'

// Season dates: mirrors the iOS 2.1.3 rules (SeasonDisplay / SeasonFilter in
// ios/.../Models/Resort.swift). Keep the two in sync.

const SEASON_STATUSES: readonly SeasonStatus[] = [
  'pre_season',
  'open',
  'closing_soon',
  'post_season',
  'temporarily_closed',
]

/** What the app shows for a resort's season. Null (no badge) for resorts that
 * are open with no closing date in sight, or without date data. */
export type SeasonDisplay =
  /** Not open yet; projected/announced opening date ahead (0 = today). */
  | { kind: 'opensOn'; date: Date; daysUntil: number }
  /** Pre-season, but the projected opening date has passed (delayed). */
  | { kind: 'notOpenYet' }
  /** Open; closing date within CLOSING_NOTE_DAYS (0 = today). */
  | { kind: 'closesOn'; date: Date; daysUntil: number }
  /** Season is over (closing date passed or resort reported closed). */
  | { kind: 'closedForSeason' }
  /** In season but temporarily closed. */
  | { kind: 'temporarilyClosed' }

export type SeasonFilter = 'all' | 'open_now' | 'opening_soon'

/** Show "in N days" only when the date is near. */
export const COUNTDOWN_DAYS = 30
/** Open resorts get a "Closes <date>" note within this many days of closing. */
export const CLOSING_NOTE_DAYS = 45
/** "Opening soon" = projected opening within this many days. */
export const OPENING_SOON_DAYS = 14

const MS_PER_DAY = 24 * 60 * 60 * 1000

/** Season dates are calendar days: parse them as UTC midnight so the day never
 * shifts with the browser's timezone. */
export function parseSeasonDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!m) return null
  const [year, month, day] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const date = new Date(Date.UTC(year, month - 1, day))
  // Reject impossible dates (e.g. 2026-02-30) instead of rolling over.
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null
  }
  return date
}

const seasonDateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})

/** "Dec 4" */
export function formatSeasonDate(date: Date): string {
  return seasonDateFormatter.format(date)
}

export function seasonStatus(resort: Pick<Resort, 'season_status'>): SeasonStatus | null {
  const raw = resort.season_status
  return raw && SEASON_STATUSES.includes(raw) ? raw : null
}

/** Today's calendar date in `timezone` (falls back to the browser's), as UTC midnight. */
function todayIn(timezone: string | undefined, now: Date): Date {
  let parts: Intl.DateTimeFormatPart[]
  try {
    parts = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone || undefined,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(now)
  } catch {
    parts = new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(now)
  }
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value)
  return new Date(Date.UTC(get('year'), get('month') - 1, get('day')))
}

/** Whole days from today (in the resort's timezone) to a season date. */
export function daysUntil(day: Date, timezone: string | undefined, now: Date = new Date()): number {
  return Math.round((day.getTime() - todayIn(timezone, now).getTime()) / MS_PER_DAY)
}

type SeasonFields = Pick<Resort, 'season_status' | 'opening_date' | 'closing_date' | 'timezone'>

/** The season badge to show, based on the server status. Dates are re-checked
 * locally so a long-open tab stays right across midnight. */
export function getSeasonDisplay(resort: SeasonFields, now: Date = new Date()): SeasonDisplay | null {
  const status = seasonStatus(resort)
  if (!status) return null
  const closing = parseSeasonDate(resort.closing_date)
  const closingIn = closing ? daysUntil(closing, resort.timezone, now) : null
  if (closingIn != null && closingIn < 0) {
    return { kind: 'closedForSeason' }
  }
  switch (status) {
    case 'pre_season': {
      const opening = parseSeasonDate(resort.opening_date)
      if (opening) {
        const days = daysUntil(opening, resort.timezone, now)
        return days >= 0 ? { kind: 'opensOn', date: opening, daysUntil: days } : { kind: 'notOpenYet' }
      }
      return { kind: 'notOpenYet' }
    }
    case 'post_season':
      return { kind: 'closedForSeason' }
    case 'temporarily_closed':
      return { kind: 'temporarilyClosed' }
    case 'closing_soon':
    case 'open':
      if (closing && closingIn != null && closingIn <= CLOSING_NOTE_DAYS) {
        return { kind: 'closesOn', date: closing, daysUntil: closingIn }
      }
      return null
  }
}

/** Not skiable right now: the season badge replaces the snow score as the
 * dominant status on cards and the detail header. */
export function isSeasonClosed(display: SeasonDisplay | null | undefined): boolean {
  return display != null && display.kind !== 'closesOn'
}

export function seasonTitle(display: SeasonDisplay): string {
  switch (display.kind) {
    case 'opensOn':
      return `Opens ${formatSeasonDate(display.date)}`
    case 'notOpenYet':
      return 'Not open yet'
    case 'closesOn':
      return `Closes ${formatSeasonDate(display.date)}`
    case 'closedForSeason':
      return 'Closed for season'
    case 'temporarilyClosed':
      return 'Temporarily closed'
  }
}

/** "today" / "tomorrow" / "in N days" for near dates, otherwise null. */
export function seasonCountdown(display: SeasonDisplay): string | null {
  if (display.kind !== 'opensOn' && display.kind !== 'closesOn') return null
  const days = display.daysUntil
  if (days === 0) return 'today'
  if (days === 1) return 'tomorrow'
  if (days >= 2 && days <= COUNTDOWN_DAYS) return `in ${days} days`
  return null
}

/** Known to be open today (resorts without season data are not counted). */
export function isOpenNow(resort: SeasonFields, now: Date = new Date()): boolean {
  const status = seasonStatus(resort)
  if (status !== 'open' && status !== 'closing_soon') return false
  const closing = parseSeasonDate(resort.closing_date)
  if (closing && daysUntil(closing, resort.timezone, now) < 0) return false
  return true
}

export function matchesSeasonFilter(resort: SeasonFields, filter: SeasonFilter, now: Date = new Date()): boolean {
  switch (filter) {
    case 'all':
      return true
    case 'open_now':
      return isOpenNow(resort, now)
    case 'opening_soon': {
      const display = getSeasonDisplay(resort, now)
      return display?.kind === 'opensOn' && display.daysUntil <= OPENING_SOON_DAYS
    }
  }
}

export const SEASON_FILTERS: readonly SeasonFilter[] = ['all', 'open_now', 'opening_soon']

export const SEASON_FILTER_LABELS: Record<SeasonFilter, string> = {
  all: 'All',
  open_now: 'Open now',
  opening_soon: 'Opening soon',
}

const SEASON_FILTER_STORAGE_KEY = 'pc_season_filter'

export function loadSeasonFilter(): SeasonFilter {
  try {
    const stored = localStorage.getItem(SEASON_FILTER_STORAGE_KEY)
    return SEASON_FILTERS.includes(stored as SeasonFilter) ? (stored as SeasonFilter) : 'all'
  } catch {
    return 'all'
  }
}

export function saveSeasonFilter(filter: SeasonFilter) {
  try {
    localStorage.setItem(SEASON_FILTER_STORAGE_KEY, filter)
  } catch {
    /* ignore (private mode / storage disabled) */
  }
}
