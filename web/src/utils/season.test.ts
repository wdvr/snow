import { describe, expect, it, beforeEach } from 'vitest'
import type { Resort } from '../api/types'
import {
  daysUntil,
  formatSeasonDate,
  getSeasonDisplay,
  isOpenNow,
  isSeasonClosed,
  loadSeasonFilter,
  matchesSeasonFilter,
  parseSeasonDate,
  saveSeasonFilter,
  seasonCountdown,
  seasonTitle,
  SEASON_FILTERS,
} from './season'

// Ported from the iOS SeasonDatesTests (PowderChaserTests.swift, 2.1.3).

/** Noon UTC on the given day; resorts below use UTC so "today" is stable. */
const day = (s: string) => new Date(`${s}T12:00:00Z`)

function resort(
  status: string | null,
  opening: string | null = null,
  closing: string | null = null,
  timezone = 'UTC',
): Pick<Resort, 'season_status' | 'opening_date' | 'closing_date' | 'timezone'> {
  return {
    season_status: status as Resort['season_status'],
    opening_date: opening,
    closing_date: closing,
    timezone,
  }
}

describe('season display', () => {
  it('shows nothing for resorts without season data', () => {
    expect(getSeasonDisplay(resort(null))).toBeNull()
    expect(getSeasonDisplay({ timezone: 'Asia/Tokyo' })).toBeNull()
    expect(isOpenNow(resort(null))).toBe(false)
  })

  it('ignores unknown statuses', () => {
    expect(getSeasonDisplay(resort('something_new', '2026-12-04'))).toBeNull()
  })

  it('pre-season shows the opening date and countdown', () => {
    const display = getSeasonDisplay(resort('pre_season', '2026-12-04', '2027-04-11'), day('2026-11-17'))
    expect(display).toMatchObject({ kind: 'opensOn', daysUntil: 17 })
    expect(isSeasonClosed(display)).toBe(true)
    expect(seasonCountdown(display!)).toBe('in 17 days')
    expect(seasonTitle(display!)).toBe('Opens Dec 4')
  })

  it('shows the countdown only when near', () => {
    const now = day('2026-11-17')
    expect(seasonCountdown(getSeasonDisplay(resort('pre_season', '2027-06-05'), now)!)).toBeNull()
    expect(seasonCountdown(getSeasonDisplay(resort('pre_season', '2026-12-17'), now)!)).toBe('in 30 days')
    expect(seasonCountdown(getSeasonDisplay(resort('pre_season', '2026-12-18'), now)!)).toBeNull()
    expect(seasonCountdown(getSeasonDisplay(resort('pre_season', '2026-11-19'), now)!)).toBe('in 2 days')
    expect(seasonCountdown(getSeasonDisplay(resort('pre_season', '2026-11-18'), now)!)).toBe('tomorrow')
    expect(seasonCountdown(getSeasonDisplay(resort('pre_season', '2026-11-17'), now)!)).toBe('today')
  })

  it('shows "Not open yet" when the projected opening has passed', () => {
    const r = resort('pre_season', '2026-11-14', '2027-04-11')
    expect(getSeasonDisplay(r, day('2026-11-17'))).toEqual({ kind: 'notOpenYet' })
    expect(isOpenNow(r, day('2026-11-17'))).toBe(false)
  })

  it('shows "Not open yet" for pre-season without an opening date', () => {
    expect(getSeasonDisplay(resort('pre_season'), day('2026-11-17'))).toEqual({ kind: 'notOpenYet' })
  })

  it('open resorts get no badge until closing is near', () => {
    const r = resort('open', '2026-11-05', '2027-06-06')
    expect(getSeasonDisplay(r, day('2027-01-10'))).toBeNull()
    expect(isOpenNow(r, day('2027-01-10'))).toBe(true)
  })

  it('open resorts without a closing date get no badge', () => {
    expect(getSeasonDisplay(resort('open', '2026-11-05'), day('2027-01-10'))).toBeNull()
  })

  it('closing soon shows the closing date as a note, not a closed badge', () => {
    const r = resort('closing_soon', '2026-12-04', '2027-04-11')
    const display = getSeasonDisplay(r, day('2027-03-20'))
    expect(display).toMatchObject({ kind: 'closesOn', daysUntil: 22 })
    expect(isSeasonClosed(display)).toBe(false)
    expect(seasonTitle(display!)).toBe('Closes Apr 11')
    expect(isOpenNow(r, day('2027-03-20'))).toBe(true)
  })

  it('uses a 45-day window for the closing note on open resorts', () => {
    const r = resort('open', '2026-12-04', '2027-04-11')
    // Apr 11 - 45 days = Feb 25
    expect(getSeasonDisplay(r, day('2027-02-25'))).toMatchObject({ kind: 'closesOn', daysUntil: 45 })
    expect(getSeasonDisplay(r, day('2027-02-24'))).toBeNull()
    expect(getSeasonDisplay(r, day('2027-04-11'))).toMatchObject({ kind: 'closesOn', daysUntil: 0 })
  })

  it('a passed closing date is closed for season even with a stale status', () => {
    const r = resort('closing_soon', '2026-12-04', '2027-04-11')
    expect(getSeasonDisplay(r, day('2027-04-12'))).toEqual({ kind: 'closedForSeason' })
    expect(isOpenNow(r, day('2027-04-12'))).toBe(false)
  })

  it('handles post-season and temporarily closed', () => {
    const now = day('2026-11-17')
    const post = getSeasonDisplay(resort('post_season', '2026-06-13', '2026-10-04'), now)
    expect(post).toEqual({ kind: 'closedForSeason' })
    expect(seasonTitle(post!)).toBe('Closed for season')
    const temp = getSeasonDisplay(resort('temporarily_closed', '2026-06-19', '2026-12-01'), now)
    expect(temp).toEqual({ kind: 'temporarilyClosed' })
    expect(seasonTitle(temp!)).toBe('Temporarily closed')
    expect(isSeasonClosed(temp)).toBe(true)
    expect(seasonCountdown(temp!)).toBeNull()
  })
})

describe('dates', () => {
  it('counts days in the resort timezone', () => {
    // 03:00 UTC Dec 4 is still Dec 3 in California: opening is tomorrow there
    const now = new Date('2026-12-04T03:00:00Z')
    expect(daysUntil(parseSeasonDate('2026-12-04')!, 'America/Los_Angeles', now)).toBe(1)
    expect(daysUntil(parseSeasonDate('2026-12-04')!, 'UTC', now)).toBe(0)
    // ...and already Dec 4 evening in Tokyo
    expect(daysUntil(parseSeasonDate('2026-12-05')!, 'Asia/Tokyo', now)).toBe(1)
  })

  it('falls back to the browser timezone for an invalid resort timezone', () => {
    expect(() => daysUntil(parseSeasonDate('2026-12-04')!, 'Not/AZone', day('2026-11-17'))).not.toThrow()
  })

  it('counts across a DST change without drifting', () => {
    // US DST ends Nov 1 2026: still whole days
    expect(daysUntil(parseSeasonDate('2026-11-20')!, 'America/Los_Angeles', day('2026-10-20'))).toBe(31)
  })

  it('parses calendar dates and rejects junk', () => {
    expect(parseSeasonDate('2026-12-04')?.toISOString()).toBe('2026-12-04T00:00:00.000Z')
    expect(parseSeasonDate('2026-12-04T00:00:00')?.toISOString()).toBe('2026-12-04T00:00:00.000Z')
    expect(parseSeasonDate('2026-02-30')).toBeNull()
    expect(parseSeasonDate('Dec 4')).toBeNull()
    expect(parseSeasonDate('')).toBeNull()
    expect(parseSeasonDate(null)).toBeNull()
    expect(parseSeasonDate(undefined)).toBeNull()
  })

  it('formats without shifting the day', () => {
    expect(formatSeasonDate(parseSeasonDate('2026-12-04')!)).toBe('Dec 4')
    expect(formatSeasonDate(parseSeasonDate('2027-01-01')!)).toBe('Jan 1')
  })
})

describe('season filter', () => {
  it('matches like the iOS filter', () => {
    const now = day('2026-11-17')
    const open = resort('open', '2026-11-05', '2027-06-06')
    const closingSoon = resort('closing_soon', '2026-11-05', '2026-12-06')
    const soon = resort('pre_season', '2026-11-25', '2027-05-23')
    const edge = resort('pre_season', '2026-12-01', '2027-05-23') // exactly 14 days
    const later = resort('pre_season', '2026-12-11', '2027-03-14') // 24 days out
    const delayed = resort('pre_season', '2026-11-10', '2027-03-14')
    const unknown = resort(null)

    expect(matchesSeasonFilter(unknown, 'all', now)).toBe(true)
    expect(matchesSeasonFilter(open, 'open_now', now)).toBe(true)
    expect(matchesSeasonFilter(closingSoon, 'open_now', now)).toBe(true)
    expect(matchesSeasonFilter(soon, 'open_now', now)).toBe(false)
    expect(matchesSeasonFilter(unknown, 'open_now', now)).toBe(false)
    expect(matchesSeasonFilter(soon, 'opening_soon', now)).toBe(true)
    expect(matchesSeasonFilter(edge, 'opening_soon', now)).toBe(true)
    expect(matchesSeasonFilter(later, 'opening_soon', now)).toBe(false)
    expect(matchesSeasonFilter(delayed, 'opening_soon', now)).toBe(false)
    expect(matchesSeasonFilter(open, 'opening_soon', now)).toBe(false)
    expect(matchesSeasonFilter(unknown, 'opening_soon', now)).toBe(false)
  })

  describe('persistence', () => {
    let store: Record<string, string>
    beforeEach(() => {
      store = {}
      globalThis.localStorage = {
        getItem: (k: string) => store[k] ?? null,
        setItem: (k: string, v: string) => {
          store[k] = v
        },
        removeItem: (k: string) => {
          delete store[k]
        },
        clear: () => {
          store = {}
        },
        key: () => null,
        length: 0,
      } as Storage
    })

    it('round-trips every filter value', () => {
      for (const filter of SEASON_FILTERS) {
        saveSeasonFilter(filter)
        expect(loadSeasonFilter()).toBe(filter)
      }
    })

    it('defaults to all for missing or unknown values', () => {
      expect(loadSeasonFilter()).toBe('all')
      store.pc_season_filter = 'bogus'
      expect(loadSeasonFilter()).toBe('all')
    })
  })
})
