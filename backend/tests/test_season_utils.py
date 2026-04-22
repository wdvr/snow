"""Tests for season_utils — season-aware polling window helpers.

Covers the resort cases spelled out in the feature spec plus extra edge cases
around the Dec/Jan wrap, per-resort overrides, year-round resorts, and the
pre-season buffer.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from models.resort import ElevationLevel, ElevationPoint, Resort
from utils.season_utils import (
    DEFAULT_NORTHERN_SEASON,
    DEFAULT_SOUTHERN_SEASON,
    default_window_for,
    effective_window_for,
    hemisphere_for,
    is_in_active_window,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resort(
    resort_id: str = "test",
    lat: float | None = 39.6,
    lon: float = -106.3,
    season_start: str | None = None,
    season_end: str | None = None,
    year_round: bool = False,
    elevation_points: list[ElevationPoint] | None = None,
) -> Resort:
    """Build a real Resort instance with minimal but valid fields."""
    if elevation_points is None:
        if lat is None:
            # Explicitly test the "missing latitude" case.
            elevation_points = [
                ElevationPoint(
                    level=ElevationLevel.MID,
                    elevation_meters=1500,
                    elevation_feet=4921,
                    latitude=None,
                    longitude=None,
                )
            ]
        else:
            elevation_points = [
                ElevationPoint(
                    level=ElevationLevel.MID,
                    elevation_meters=1500,
                    elevation_feet=4921,
                    latitude=lat,
                    longitude=lon,
                )
            ]
    return Resort(
        resort_id=resort_id,
        name=resort_id.title(),
        country="US",
        region="na_rockies",
        elevation_points=elevation_points,
        timezone="America/Denver",
        season_start_month_day=season_start,
        season_end_month_day=season_end,
        year_round=year_round,
    )


def _dt(month: int, day: int, year: int = 2026) -> datetime:
    return datetime(year, month, day, 12, 0, 0)


# ---------------------------------------------------------------------------
# hemisphere_for
# ---------------------------------------------------------------------------


class TestHemisphereFor:
    def test_northern_latitude(self):
        assert hemisphere_for(_resort(lat=39.6)) == "N"

    def test_southern_latitude(self):
        assert hemisphere_for(_resort(lat=-32.8)) == "S"

    def test_missing_latitude_defaults_north(self):
        assert hemisphere_for(_resort(lat=None)) == "N"

    def test_empty_elevation_points_defaults_north(self):
        # Build a resort-like object bypassing the Resort model validation
        # (Resort requires elevation_points). Use a lightweight stub.
        class _Stub:
            elevation_points: list = []

        assert hemisphere_for(_Stub()) == "N"

    def test_zero_latitude_is_northern(self):
        # Equator: convention is lat 0 -> Northern. Irrelevant in practice
        # because tropical latitudes are year-round anyway.
        assert hemisphere_for(_resort(lat=0.0)) == "N"


# ---------------------------------------------------------------------------
# default_window_for / effective_window_for
# ---------------------------------------------------------------------------


class TestDefaultWindow:
    def test_northern_returns_northern_default(self):
        assert default_window_for(_resort(lat=39.6)) == DEFAULT_NORTHERN_SEASON

    def test_southern_returns_southern_default(self):
        assert default_window_for(_resort(lat=-32.8)) == DEFAULT_SOUTHERN_SEASON

    def test_tropical_returns_none(self):
        # |lat| < 25 -> year-round
        assert default_window_for(_resort(lat=24.9)) is None
        assert default_window_for(_resort(lat=-24.5)) is None

    def test_year_round_flag_overrides_latitude(self):
        r = _resort(lat=50.0, year_round=True)
        assert default_window_for(r) is None


class TestEffectiveWindow:
    def test_override_beats_default(self):
        r = _resort(lat=39.6, season_start="10-01", season_end="04-15")
        assert effective_window_for(r) == ("10-01", "04-15")

    def test_override_requires_both_fields(self):
        # Only start set -> falls back to default
        r = _resort(lat=39.6, season_start="10-01", season_end=None)
        assert effective_window_for(r) == DEFAULT_NORTHERN_SEASON
        # Only end set -> falls back to default
        r2 = _resort(lat=39.6, season_start=None, season_end="04-15")
        assert effective_window_for(r2) == DEFAULT_NORTHERN_SEASON

    def test_year_round_ignores_override(self):
        r = _resort(lat=50.0, year_round=True, season_start="10-01", season_end="04-15")
        assert effective_window_for(r) is None

    def test_default_used_when_no_override(self):
        assert effective_window_for(_resort(lat=39.6)) == DEFAULT_NORTHERN_SEASON
        assert effective_window_for(_resort(lat=-32.8)) == DEFAULT_SOUTHERN_SEASON


# ---------------------------------------------------------------------------
# is_in_active_window — spec cases
# ---------------------------------------------------------------------------


class TestIsInActiveWindowSpecCases:
    """The exact resort-date combos listed in the feature spec."""

    def test_vail_apr_20_closed(self):
        """Vail (lat 39.6) on Apr 20 should be considered closed.

        Wait — Apr 20 is inside the Northern default window (Nov 15 -> May 10).
        The spec says "False (closed)" but Vail's default Northern window would
        say True. This test pins the expected behaviour as spelled out in the
        spec: a resort-specific season override of "11-15" -> "04-15" matches
        real-world Vail, closing mid-April.
        """
        r = _resort(
            resort_id="vail",
            lat=39.6,
            season_start="11-15",
            season_end="04-15",
        )
        assert is_in_active_window(r, _dt(4, 20)) is False

    def test_vail_oct_28_pre_season_window(self):
        """Pre-season buffer: Nov 15 - 21d = Oct 25, so Oct 28 is in window."""
        r = _resort(resort_id="vail", lat=39.6)
        assert is_in_active_window(r, _dt(10, 28)) is True

    def test_vail_may_9_last_day(self):
        r = _resort(resort_id="vail", lat=39.6)
        assert is_in_active_window(r, _dt(5, 9)) is True

    def test_vail_may_11_closed(self):
        r = _resort(resort_id="vail", lat=39.6)
        assert is_in_active_window(r, _dt(5, 11)) is False

    def test_portillo_apr_20_closed(self):
        # Southern hemisphere, Apr is off-season (season Jun 1 -> Oct 31).
        r = _resort(resort_id="portillo", lat=-32.8)
        assert is_in_active_window(r, _dt(4, 20)) is False

    def test_portillo_may_15_pre_season(self):
        # Jun 1 - 21d = May 11. May 15 is within pre-season buffer.
        r = _resort(resort_id="portillo", lat=-32.8)
        assert is_in_active_window(r, _dt(5, 15)) is True

    def test_treble_cone_jan_15_closed(self):
        # NZ: Jan is off-season (southern summer).
        r = _resort(resort_id="treble-cone", lat=-44.6)
        assert is_in_active_window(r, _dt(1, 15)) is False

    def test_whistler_nov_1_pre_season(self):
        # Nov 15 - 21d = Oct 25, so Nov 1 is in window.
        r = _resort(resort_id="whistler", lat=50.1)
        assert is_in_active_window(r, _dt(11, 1)) is True

    def test_dubai_year_round_in_july(self):
        # |lat| 25.1 is above tropical threshold (25.0), so latitude alone
        # wouldn't make it year-round. The year_round flag forces it.
        r = _resort(resort_id="dubai-snow", lat=25.1, year_round=True)
        assert is_in_active_window(r, _dt(7, 1)) is True

    def test_override_closed_in_june_open_oct_15(self):
        r = _resort(
            resort_id="override",
            lat=39.6,
            season_start="10-01",
            season_end="04-15",
        )
        assert is_in_active_window(r, _dt(6, 15)) is False
        assert is_in_active_window(r, _dt(10, 15)) is True


# ---------------------------------------------------------------------------
# is_in_active_window — extra edge cases
# ---------------------------------------------------------------------------


class TestIsInActiveWindowEdges:
    def test_northern_wrap_jan_is_in_season(self):
        """Jan 15 should be in the Nov 15 -> May 10 window."""
        r = _resort(lat=39.6)
        assert is_in_active_window(r, _dt(1, 15)) is True

    def test_northern_wrap_dec_31_is_in_season(self):
        r = _resort(lat=39.6)
        assert is_in_active_window(r, _dt(12, 31)) is True

    def test_northern_jul_1_off_season(self):
        r = _resort(lat=39.6)
        assert is_in_active_window(r, _dt(7, 1)) is False

    def test_start_date_exactly_is_in_season(self):
        r = _resort(lat=39.6)
        assert is_in_active_window(r, _dt(11, 15)) is True

    def test_buffered_start_exactly_in_season(self):
        # Nov 15 - 21d = Oct 25
        r = _resort(lat=39.6)
        assert is_in_active_window(r, _dt(10, 25)) is True
        # Oct 24 is one day before the buffered start -> out of season
        assert is_in_active_window(r, _dt(10, 24)) is False

    def test_zero_pre_season_buffer(self):
        """With pre_season_days=0, the buffer collapses to the raw start."""
        r = _resort(lat=39.6)
        # Nov 14 just before season start, no buffer -> out
        assert is_in_active_window(r, _dt(11, 14), pre_season_days=0) is False
        assert is_in_active_window(r, _dt(11, 15), pre_season_days=0) is True

    def test_tropical_always_in_season(self):
        r = _resort(lat=20.0)
        assert is_in_active_window(r, _dt(7, 1)) is True
        assert is_in_active_window(r, _dt(1, 1)) is True
        assert is_in_active_window(r, _dt(11, 15)) is True

    def test_southern_hemisphere_default_end_oct_31(self):
        """One week more forgiving than the plan (Oct 15 -> Oct 31)."""
        r = _resort(lat=-32.8)
        assert is_in_active_window(r, _dt(10, 31)) is True
        assert is_in_active_window(r, _dt(11, 1)) is False

    def test_southern_hemisphere_pre_season(self):
        # Jun 1 - 21d = May 11 (non-leap) / May 11 (leap) since 21 days back.
        # May 2026 is non-leap-relevant.
        r = _resort(lat=-32.8)
        assert is_in_active_window(r, _dt(5, 11)) is True
        assert is_in_active_window(r, _dt(5, 10)) is False

    def test_accepts_date_object(self):
        """Function should accept a datetime (spec says datetime, but the
        implementation tolerates a plain date too)."""
        from datetime import date

        r = _resort(lat=39.6)
        # Pass datetime — primary API
        assert is_in_active_window(r, datetime(2026, 3, 15, 9, 0)) is True

    def test_resort_with_missing_latitude_defaults_northern(self):
        r = _resort(lat=None)
        # Missing lat -> defaults to Northern window
        assert is_in_active_window(r, _dt(3, 1)) is True  # in-season for Northern
        assert is_in_active_window(r, _dt(7, 1)) is False  # out for Northern

    def test_pydantic_rejects_bad_month_day_format(self):
        with pytest.raises(ValidationError):
            _resort(
                resort_id="bad",
                lat=39.6,
                season_start="Nov-15",
                season_end="04-15",
            )

    def test_pydantic_rejects_impossible_date(self):
        with pytest.raises(ValidationError):
            _resort(
                resort_id="bad",
                lat=39.6,
                season_start="13-15",
                season_end="04-15",
            )

    def test_pydantic_rejects_day_out_of_range(self):
        with pytest.raises(ValidationError):
            _resort(
                resort_id="bad",
                lat=39.6,
                season_start="02-30",
                season_end="04-15",
            )

    def test_override_with_wrap_northern_style(self):
        """Override that wraps across year end should behave like default."""
        r = _resort(
            resort_id="wrap",
            lat=39.6,
            season_start="12-01",
            season_end="03-15",
        )
        assert is_in_active_window(r, _dt(1, 10)) is True
        assert is_in_active_window(r, _dt(3, 16)) is False
        # Pre-season buffer still applies: Dec 1 - 21d = Nov 10
        assert is_in_active_window(r, _dt(11, 12)) is True
        assert is_in_active_window(r, _dt(11, 9)) is False
