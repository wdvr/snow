import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import type { Resort, SnowQualitySummary } from '../../api/types'
import { UnitProvider } from '../../hooks/useUnits'
import { ResortCard } from './ResortCard'

const baseResort: Resort = {
  resort_id: 'kirkwood',
  name: 'Kirkwood Mountain Resort',
  country: 'US',
  region: 'na_west',
  elevation_points: [],
  timezone: 'America/Los_Angeles',
  official_website: null,
  logo_url: null,
  trail_map_url: null,
  webcam_url: null,
  green_runs_pct: null,
  blue_runs_pct: null,
  black_runs_pct: null,
  weather_sources: [],
  created_at: null,
  updated_at: null,
  epic_pass: 'Full',
  ikon_pass: null,
  indy_pass: null,
}

const quality = {
  resort_id: 'kirkwood',
  overall_quality: 'powder_day',
  snow_score: 91,
  snowfall_fresh_cm: 20,
  temperature_c: -4,
  snow_depth_cm: 80,
} as SnowQualitySummary

function render(resort: Resort, q: SnowQualitySummary | null = quality) {
  return renderToStaticMarkup(
    <MemoryRouter>
      <UnitProvider>
        <ResortCard resort={resort} quality={q ?? undefined} />
      </UnitProvider>
    </MemoryRouter>,
  )
}

/** Visible text only, tags stripped. */
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')

describe('ResortCard season dates', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Nov 17 2026, 10:00 in California
    vi.setSystemTime(new Date('2026-11-17T18:00:00Z'))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('looks exactly as before for resorts without season data', () => {
    const html = render(baseResort)
    expect(html).not.toContain('data-testid="season-badge"')
    expect(html).not.toContain('data-testid="season-note"')
    expect(html).not.toContain('data-testid="secondary-score"')
    expect(text(html)).toContain('Powder Day 91')
  })

  it('closed resort leads with the opening badge and mutes the score', () => {
    const html = render({
      ...baseResort,
      opening_date: '2026-12-04',
      closing_date: '2027-04-11',
      season_status: 'pre_season',
      season_dates_source: 'onthesnow',
    })
    expect(html).toContain('data-testid="season-badge"')
    expect(text(html)).toContain('Opens Dec 4')
    expect(text(html)).toContain('in 17 days')
    expect(html).toContain('data-testid="secondary-score"')
    expect(html).toContain('aria-label="Snow forecast: Powder Day, score 91"')
    // The coloured quality pill is replaced
    expect(html).not.toContain('rounded-full font-semibold text-white')
  })

  it('closed resort without a score shows only the badge', () => {
    const html = render(
      { ...baseResort, opening_date: '2026-12-04', closing_date: '2027-04-11', season_status: 'pre_season' },
      null,
    )
    expect(html).toContain('data-testid="season-badge"')
    expect(html).not.toContain('data-testid="secondary-score"')
  })

  it('open resort closing soon keeps the score and adds a closes note', () => {
    vi.setSystemTime(new Date('2027-03-20T18:00:00Z'))
    const html = render({
      ...baseResort,
      opening_date: '2026-12-04',
      closing_date: '2027-04-11',
      season_status: 'closing_soon',
    })
    expect(html).not.toContain('data-testid="season-badge"')
    expect(html).toContain('data-testid="season-note"')
    expect(text(html)).toContain('Closes Apr 11')
    expect(text(html)).toContain('in 22 days')
    expect(text(html)).toContain('Powder Day 91')
  })

  it('open resort mid-season shows no season UI', () => {
    vi.setSystemTime(new Date('2027-01-10T18:00:00Z'))
    const html = render({
      ...baseResort,
      opening_date: '2026-11-13',
      closing_date: '2027-04-11',
      season_status: 'open',
    })
    expect(html).not.toContain('data-testid="season-badge"')
    expect(html).not.toContain('data-testid="season-note"')
  })
})
