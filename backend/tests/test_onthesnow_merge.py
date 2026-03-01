"""Tests for OnTheSnow scraper: JSON extraction, regex fallback, and merge logic.

Covers:
- JSON extraction from __NEXT_DATA__ script tag (primary path)
- Regex-based HTML parsing (fallback path)
- merge_with_weather_data snow_depth integration
- Resort URL mapping completeness

Regression history:
- Scraper stored depths only in raw_data, causing HORRIBLE ratings for resorts
  with actual snow (Palisades Tahoe 28" base, Vail 65", Steamboat 57").
- Regex was too greedy: matched lifts count as base depth, copyright year as summit.
"""

import json

from services.onthesnow_scraper import (
    RESORT_URL_MAPPING,
    OnTheSnowScraper,
    ScrapedSnowData,
)


def _make_scraped_data(
    base_depth_inches: float | None = None,
    summit_depth_inches: float | None = None,
    **kwargs,
) -> ScrapedSnowData:
    """Create a ScrapedSnowData with sensible defaults."""
    return ScrapedSnowData(
        resort_id=kwargs.get("resort_id", "test-resort"),
        snowfall_24h_inches=kwargs.get("snowfall_24h_inches", None),
        snowfall_48h_inches=kwargs.get("snowfall_48h_inches", None),
        snowfall_72h_inches=kwargs.get("snowfall_72h_inches", None),
        base_depth_inches=base_depth_inches,
        summit_depth_inches=summit_depth_inches,
        surface_conditions=kwargs.get("surface_conditions", None),
        lifts_open=kwargs.get("lifts_open", None),
        lifts_total=kwargs.get("lifts_total", None),
        runs_open=kwargs.get("runs_open", None),
        runs_total=kwargs.get("runs_total", None),
        last_updated=kwargs.get("last_updated", None),
        source_url=kwargs.get("source_url", "https://test.com"),
    )


def _make_weather_data(snow_depth_cm: float = 0.0, **overrides) -> dict:
    """Create minimal weather data dict as Open-Meteo would return."""
    data = {
        "snow_depth_cm": snow_depth_cm,
        "snowfall_24h_cm": 0.0,
        "snowfall_48h_cm": 0.0,
        "snowfall_72h_cm": 0.0,
        "source_confidence": "medium",
        "data_source": "open-meteo.com",
    }
    data.update(overrides)
    return data


class TestScrapedDepthForLevel:
    """Tests for _get_scraped_depth_for_level static method."""

    def test_base_level_gets_base_depth(self):
        scraped = _make_scraped_data(base_depth_inches=28.0, summit_depth_inches=60.0)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "base")
        assert depth == 28.0 * 2.54  # 71.12cm

    def test_top_level_gets_summit_depth(self):
        scraped = _make_scraped_data(base_depth_inches=28.0, summit_depth_inches=60.0)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "top")
        assert depth == 60.0 * 2.54  # 152.4cm

    def test_mid_level_gets_average(self):
        scraped = _make_scraped_data(base_depth_inches=28.0, summit_depth_inches=60.0)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "mid")
        expected = (28.0 * 2.54 + 60.0 * 2.54) / 2.0
        assert abs(depth - expected) < 0.01

    def test_top_falls_back_to_base_when_no_summit(self):
        scraped = _make_scraped_data(base_depth_inches=28.0, summit_depth_inches=None)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "top")
        assert depth == 28.0 * 2.54

    def test_mid_falls_back_to_base_when_no_summit(self):
        scraped = _make_scraped_data(base_depth_inches=28.0, summit_depth_inches=None)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "mid")
        assert depth == 28.0 * 2.54

    def test_mid_falls_back_to_summit_when_no_base(self):
        scraped = _make_scraped_data(base_depth_inches=None, summit_depth_inches=60.0)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "mid")
        assert depth == 60.0 * 2.54

    def test_base_returns_none_when_no_data(self):
        scraped = _make_scraped_data(base_depth_inches=None, summit_depth_inches=None)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "base")
        assert depth is None

    def test_top_returns_none_when_no_data(self):
        scraped = _make_scraped_data(base_depth_inches=None, summit_depth_inches=None)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "top")
        assert depth is None

    def test_mid_returns_none_when_no_data(self):
        scraped = _make_scraped_data(base_depth_inches=None, summit_depth_inches=None)
        depth = OnTheSnowScraper._get_scraped_depth_for_level(scraped, "mid")
        assert depth is None


class TestMergeSnowDepth:
    """Tests for merge_with_weather_data snow_depth promotion."""

    def test_palisades_tahoe_base_scenario(self):
        """Regression: Palisades Tahoe base had 28" (71cm) but API showed 0cm HORRIBLE.

        Open-Meteo reported 0cm, scraper had 28" base depth but didn't promote it.
        With the fix, merge should set snow_depth_cm to 71.12cm for base level.
        """
        scraper = OnTheSnowScraper()
        weather = _make_weather_data(snow_depth_cm=0.0)
        scraped = _make_scraped_data(
            resort_id="palisades-tahoe",
            base_depth_inches=28.0,
            summit_depth_inches=60.0,
        )

        merged = scraper.merge_with_weather_data(
            weather, scraped, elevation_level="base"
        )

        assert merged["snow_depth_cm"] == 28.0 * 2.54  # 71.12cm, not 0
        assert merged["source_confidence"].value == "high"

    def test_vail_base_overrides_zero_depth(self):
        """Regression: Vail base showed HORRIBLE due to 0cm model depth."""
        scraper = OnTheSnowScraper()
        weather = _make_weather_data(snow_depth_cm=0.0)
        scraped = _make_scraped_data(
            resort_id="vail",
            base_depth_inches=65.0,
            summit_depth_inches=65.0,
        )

        merged = scraper.merge_with_weather_data(
            weather, scraped, elevation_level="base"
        )

        assert merged["snow_depth_cm"] == 65.0 * 2.54  # 165.1cm
        assert merged["snow_depth_cm"] > 100  # Deep base, should get boost

    def test_scraped_depth_overrides_model_depth(self):
        """Scraped depth should override even non-zero model depth."""
        scraper = OnTheSnowScraper()
        weather = _make_weather_data(snow_depth_cm=5.0)  # Model says 5cm
        scraped = _make_scraped_data(
            base_depth_inches=40.0
        )  # Resort says 40" = 101.6cm

        merged = scraper.merge_with_weather_data(
            weather, scraped, elevation_level="base"
        )

        assert merged["snow_depth_cm"] == 40.0 * 2.54  # 101.6cm, not 5cm

    def test_no_scraped_depth_keeps_model_depth(self):
        """When scraper has no depth data, model depth is preserved."""
        scraper = OnTheSnowScraper()
        weather = _make_weather_data(snow_depth_cm=52.0)
        scraped = _make_scraped_data(base_depth_inches=None, summit_depth_inches=None)

        merged = scraper.merge_with_weather_data(
            weather, scraped, elevation_level="base"
        )

        assert merged["snow_depth_cm"] == 52.0  # Unchanged

    def test_elevation_level_defaults_to_mid(self):
        """Default elevation_level should be 'mid'."""
        scraper = OnTheSnowScraper()
        weather = _make_weather_data(snow_depth_cm=0.0)
        scraped = _make_scraped_data(base_depth_inches=28.0, summit_depth_inches=60.0)

        merged = scraper.merge_with_weather_data(weather, scraped)

        expected = (28.0 * 2.54 + 60.0 * 2.54) / 2.0  # mid = average
        assert abs(merged["snow_depth_cm"] - expected) < 0.01

    def test_raw_data_still_stored(self):
        """Scraped data should still be stored in raw_data for debugging."""
        scraper = OnTheSnowScraper()
        weather = _make_weather_data()
        scraped = _make_scraped_data(base_depth_inches=28.0, summit_depth_inches=60.0)

        merged = scraper.merge_with_weather_data(
            weather, scraped, elevation_level="base"
        )

        assert merged["raw_data"]["scraped_onthesnow"]["base_depth_inches"] == 28.0
        assert merged["raw_data"]["scraped_onthesnow"]["summit_depth_inches"] == 60.0

    def test_snowfall_still_merged(self):
        """Snowfall merging should still work alongside depth merging."""
        scraper = OnTheSnowScraper()
        weather = _make_weather_data(snow_depth_cm=0.0, snowfall_24h_cm=5.0)
        scraped = _make_scraped_data(
            base_depth_inches=28.0,
            snowfall_24h_inches=3.0,  # 7.62cm
        )

        merged = scraper.merge_with_weather_data(
            weather, scraped, elevation_level="base"
        )

        # Depth should be from scraper
        assert merged["snow_depth_cm"] == 28.0 * 2.54
        # Snowfall should be blended (70% scraped + 30% API)
        expected_snowfall = 7.62 * 0.7 + 5.0 * 0.3
        assert abs(merged["snowfall_24h_cm"] - expected_snowfall) < 0.01


class TestMergeEndToEnd:
    """End-to-end tests verifying the full quality impact of the fix."""

    def test_palisades_base_no_longer_horrible(self):
        """With scraped depth, Palisades base should NOT be HORRIBLE at warm temps."""
        from models.weather import ConfidenceLevel, WeatherCondition
        from services.snow_quality_service import SnowQualityService

        scraper = OnTheSnowScraper()
        weather_data = _make_weather_data(
            snow_depth_cm=0.0,
            current_temp_celsius=8.5,
            min_temp_celsius=2.0,
            max_temp_celsius=10.0,
            hours_above_ice_threshold=6.0,
            snowfall_after_freeze_cm=0.0,
            last_freeze_thaw_hours_ago=1.0,
        )
        scraped = _make_scraped_data(
            base_depth_inches=28.0,
            summit_depth_inches=60.0,
        )

        merged = scraper.merge_with_weather_data(
            weather_data, scraped, elevation_level="base"
        )

        condition = WeatherCondition(
            resort_id="palisades-tahoe",
            elevation_level="base",
            timestamp="2026-02-07T12:00:00+00:00",
            **merged,
        )

        quality_service = SnowQualityService()
        quality, _, _, _ = quality_service.assess_snow_quality(condition)

        # At 8.5°C with 71cm base, should be POOR (soft/warm) not HORRIBLE
        assert quality.value != "horrible", (
            f"Palisades base with 71cm scraped depth should not be HORRIBLE, got {quality.value}"
        )

    def test_steamboat_top_with_scraped_depth_not_horrible(self):
        """Steamboat top with scraped summit depth should not be HORRIBLE."""
        from models.weather import WeatherCondition
        from services.snow_quality_service import SnowQualityService

        scraper = OnTheSnowScraper()
        weather_data = _make_weather_data(
            snow_depth_cm=0.0,  # Model says 0
            current_temp_celsius=0.6,
            min_temp_celsius=-5.0,
            max_temp_celsius=2.0,
            hours_above_ice_threshold=3.0,
            snowfall_after_freeze_cm=0.0,
            last_freeze_thaw_hours_ago=47.0,
        )
        scraped = _make_scraped_data(
            base_depth_inches=57.0,
            summit_depth_inches=57.0,
        )

        merged = scraper.merge_with_weather_data(
            weather_data, scraped, elevation_level="top"
        )

        condition = WeatherCondition(
            resort_id="steamboat",
            elevation_level="top",
            timestamp="2026-02-07T12:00:00+00:00",
            **merged,
        )

        quality_service = SnowQualityService()
        quality, _, _, _ = quality_service.assess_snow_quality(condition)

        # With 57" (144.78cm) scraped depth, should NOT be HORRIBLE
        assert quality.value != "horrible", (
            f"Steamboat top with 144cm scraped depth should not be HORRIBLE, got {quality.value}"
        )


class TestSnowDepthRegexParsing:
    """Tests for the scraper regex patterns that extract depth from HTML text.

    Regression: The original regexes were too greedy:
    - Base regex matched "base depth with 25" (lifts count) instead of "37" base"
    - Summit regex matched "top of Eagle Bahn Gondola...1995" (copyright year)
    """

    def test_base_depth_data_section_format(self):
        """Parse 'Base 37" Machine Groomed' format."""
        scraper = OnTheSnowScraper()
        html = '<div>Base 37" Machine Groomed Summit 41" Packed Powder</div>'
        result = scraper._parse_snow_report(html, "test", "https://test.com")
        assert result.base_depth_inches == 37.0

    def test_summit_depth_data_section_format(self):
        """Parse 'Summit 41" Packed Powder' format."""
        scraper = OnTheSnowScraper()
        html = '<div>Base 37" Machine Groomed Summit 41" Packed Powder</div>'
        result = scraper._parse_snow_report(html, "test", "https://test.com")
        assert result.summit_depth_inches == 41.0

    def test_base_depth_inline_format(self):
        """Parse 'a 37" base depth' format."""
        scraper = OnTheSnowScraper()
        html = '<div>Vail has a 37" base depth with 25 of 33 lifts open</div>'
        result = scraper._parse_snow_report(html, "test", "https://test.com")
        assert result.base_depth_inches == 37.0

    def test_does_not_match_lifts_as_base_depth(self):
        """Regression: old regex matched lifts count (25) as base depth."""
        scraper = OnTheSnowScraper()
        # The old regex: (?:base|bottom)[^0-9]*(\d+) matched "base depth with 25"
        html = "<div>No other base info, just 25 of 33 lifts open</div>"
        result = scraper._parse_snow_report(html, "test", "https://test.com")
        assert result.base_depth_inches is None

    def test_does_not_match_copyright_as_summit(self):
        """Regression: old regex matched copyright year (1995) as summit depth."""
        scraper = OnTheSnowScraper()
        html = (
            "<div>top of Eagle Bahn Gondola offers snowmobiling. "
            "Copyright 1995-2026 OnTheSnow.com</div>"
        )
        result = scraper._parse_snow_report(html, "test", "https://test.com")
        assert result.summit_depth_inches is None

    def test_sanity_check_rejects_huge_depth(self):
        """Depth values >300" (base) or >500" (summit) are rejected."""
        scraper = OnTheSnowScraper()
        html = '<div>Base 999" Summit 999"</div>'
        result = scraper._parse_snow_report(html, "test", "https://test.com")
        assert result.base_depth_inches is None
        assert result.summit_depth_inches is None

    def test_palisades_tahoe_real_format(self):
        """Parse real Palisades Tahoe page format."""
        scraper = OnTheSnowScraper()
        html = (
            '<div>Palisades Tahoe has a 28" base depth with 34 of 37 lifts open. '
            'Base 28" Machine Groomed Summit 45" Variable Conditions</div>'
        )
        result = scraper._parse_snow_report(html, "palisades-tahoe", "https://test.com")
        assert result.base_depth_inches == 28.0
        assert result.summit_depth_inches == 45.0

    def test_no_summit_data_returns_none(self):
        """When page has no 'Summit XX"' pattern, summit should be None."""
        scraper = OnTheSnowScraper()
        html = '<div>Base 37" Machine Groomed. Top of mountain accessible by gondola.</div>'
        result = scraper._parse_snow_report(html, "test", "https://test.com")
        assert result.base_depth_inches == 37.0
        assert result.summit_depth_inches is None


# ── Helper to build __NEXT_DATA__ HTML ──────────────────────────────


def _build_next_data_html(
    snow: dict | None = None,
    depths: dict | None = None,
    lifts: dict | None = None,
    runs: dict | None = None,
    status: dict | None = None,
    updated_at: str | None = None,
    extra_html: str = "",
) -> str:
    """Build a minimal HTML page with __NEXT_DATA__ JSON for testing."""
    full_resort = {}
    if snow is not None:
        full_resort["snow"] = snow
    if depths is not None:
        full_resort["depths"] = depths
    if lifts is not None:
        full_resort["lifts"] = lifts
    if runs is not None:
        full_resort["runs"] = runs
    if status is not None:
        full_resort["status"] = status
    if updated_at is not None:
        full_resort["updatedAt"] = updated_at

    next_data = {
        "props": {
            "pageProps": {
                "type": "resort",
                "route": "skireport",
                "fullResort": full_resort,
            }
        }
    }
    json_str = json.dumps(next_data)
    return (
        f"<html><head></head><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json_str}</script>'
        f"{extra_html}</body></html>"
    )


class TestJsonExtraction:
    """Tests for the __NEXT_DATA__ JSON extraction path."""

    def test_extracts_snowfall_from_json(self):
        """Snowfall values (cm in JSON) are converted to inches."""
        scraper = OnTheSnowScraper()
        # 5.08 cm = 2 inches, 10.16 cm = 4 inches, 15.24 cm = 6 inches
        html = _build_next_data_html(
            snow={"last24": 5.08, "last48": 10.16, "last72": 15.24}
        )
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert abs(result.snowfall_24h_inches - 2.0) < 0.01
        assert abs(result.snowfall_48h_inches - 4.0) < 0.01
        assert abs(result.snowfall_72h_inches - 6.0) < 0.01

    def test_extracts_depths_from_json(self):
        """Depth values (cm in JSON) are converted to inches."""
        scraper = OnTheSnowScraper()
        # 119.38 cm = ~47 inches, 152.4 cm = 60 inches
        html = _build_next_data_html(
            depths={"base": 119.38, "middle": 135.0, "summit": 152.4}
        )
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert abs(result.base_depth_inches - 46.99) < 0.1
        assert abs(result.mid_depth_inches - 53.15) < 0.1
        assert abs(result.summit_depth_inches - 60.0) < 0.01

    def test_extracts_lifts_and_runs(self):
        """Lifts and runs are extracted as integers."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(
            lifts={"open": 28, "total": 33},
            runs={"open": 222, "total": 277, "openPercent": 80},
        )
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.lifts_open == 28
        assert result.lifts_total == 33
        assert result.runs_open == 222
        assert result.runs_total == 277

    def test_extracts_open_flag_true(self):
        """openFlag=1 maps to open_flag=True."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(status={"openFlag": 1})
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.open_flag is True

    def test_extracts_open_flag_false(self):
        """openFlag=0 maps to open_flag=False."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(status={"openFlag": 0})
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.open_flag is False

    def test_extracts_updated_at(self):
        """updatedAt ISO timestamp is stored in last_updated."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(updated_at="2026-02-28T12:25:49+00:00")
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.last_updated == "2026-02-28T12:25:49+00:00"

    def test_null_values_become_none(self):
        """Null/None JSON values result in None fields."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(
            snow={"last24": None, "last48": 0, "last72": None},
            depths={"base": None, "middle": None, "summit": None},
        )
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.snowfall_24h_inches is None
        # 0 cm -> 0 inches, not None
        assert result.snowfall_48h_inches == 0.0
        assert result.snowfall_72h_inches is None
        assert result.base_depth_inches is None
        assert result.summit_depth_inches is None

    def test_zero_snowfall_preserved(self):
        """Zero snowfall should be 0.0, not None."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(snow={"last24": 0, "last48": 0.0, "last72": 0})
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.snowfall_24h_inches == 0.0
        assert result.snowfall_48h_inches == 0.0
        assert result.snowfall_72h_inches == 0.0

    def test_missing_snow_section(self):
        """Missing snow section results in None snowfall fields."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(lifts={"open": 10, "total": 15})
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.snowfall_24h_inches is None
        assert result.lifts_open == 10

    def test_base_depth_fallback_to_snow_base(self):
        """When depths.base is null, fall back to snow.base."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(
            snow={"base": 119.38},
            depths={"base": None, "summit": None},
        )
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert abs(result.base_depth_inches - 46.99) < 0.1

    def test_full_resort_data(self):
        """Test complete resort data extraction matching real Vail structure."""
        scraper = OnTheSnowScraper()
        html = _build_next_data_html(
            snow={"last24": 0, "last48": 5.08, "last72": 10.16, "base": 119.38},
            depths={"base": 119.38, "middle": None, "summit": None},
            lifts={"open": 28, "total": 33},
            runs={"open": 222, "total": 277, "openPercent": 80},
            status={"openFlag": 1},
            updated_at="2026-02-28T12:25:49+00:00",
        )
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        assert result.resort_id == "vail"
        assert result.snowfall_24h_inches == 0.0
        assert abs(result.snowfall_48h_inches - 2.0) < 0.01
        assert abs(result.snowfall_72h_inches - 4.0) < 0.01
        assert abs(result.base_depth_inches - 46.99) < 0.1
        assert result.lifts_open == 28
        assert result.lifts_total == 33
        assert result.runs_open == 222
        assert result.runs_total == 277
        assert result.open_flag is True
        assert result.last_updated == "2026-02-28T12:25:49+00:00"
        assert result.source_url == "https://test.com"

    def test_json_preferred_over_regex(self):
        """When both JSON and regex-parseable text exist, JSON wins."""
        scraper = OnTheSnowScraper()
        # JSON says 5.08cm = 2 inches for 24h
        # HTML text says 99 inches for 24h (from regex pattern "24 hr 99")
        html = _build_next_data_html(
            snow={"last24": 5.08, "last48": 0, "last72": 0},
            extra_html='<div>24 hr 99"</div>',
        )
        result = scraper._parse_snow_report(html, "vail", "https://test.com")

        assert result is not None
        # Should use JSON value (2"), not regex value (99")
        assert abs(result.snowfall_24h_inches - 2.0) < 0.01


class TestJsonFallbackToRegex:
    """Tests that regex parsing kicks in when JSON is unavailable."""

    def test_no_next_data_falls_back_to_regex(self):
        """Without __NEXT_DATA__, regex parsing is used."""
        scraper = OnTheSnowScraper()
        html = '<div>Base 37" Machine Groomed Summit 41" Packed Powder</div>'
        result = scraper._parse_snow_report(html, "test", "https://test.com")

        assert result is not None
        assert result.base_depth_inches == 37.0
        assert result.summit_depth_inches == 41.0

    def test_malformed_json_falls_back_to_regex(self):
        """Malformed JSON in __NEXT_DATA__ triggers regex fallback."""
        scraper = OnTheSnowScraper()
        html = (
            "<html><body>"
            '<script id="__NEXT_DATA__" type="application/json">{bad json}</script>'
            '<div>Base 37" Machine Groomed</div>'
            "</body></html>"
        )
        result = scraper._parse_snow_report(html, "test", "https://test.com")

        assert result is not None
        assert result.base_depth_inches == 37.0

    def test_missing_full_resort_falls_back_to_regex(self):
        """JSON without fullResort key triggers regex fallback."""
        scraper = OnTheSnowScraper()
        next_data = json.dumps({"props": {"pageProps": {"type": "other"}}})
        html = (
            f"<html><body>"
            f'<script id="__NEXT_DATA__" type="application/json">{next_data}</script>'
            f'<div>Base 37" Machine Groomed</div>'
            f"</body></html>"
        )
        result = scraper._parse_snow_report(html, "test", "https://test.com")

        assert result is not None
        assert result.base_depth_inches == 37.0


class TestCmToInchesHelper:
    """Tests for the _cm_to_inches static method."""

    def test_converts_positive_cm(self):
        assert abs(OnTheSnowScraper._cm_to_inches(2.54) - 1.0) < 0.01

    def test_returns_none_for_none(self):
        assert OnTheSnowScraper._cm_to_inches(None) is None

    def test_returns_none_for_negative(self):
        assert OnTheSnowScraper._cm_to_inches(-5.0) is None

    def test_handles_zero(self):
        assert OnTheSnowScraper._cm_to_inches(0) == 0.0

    def test_handles_string_number(self):
        assert abs(OnTheSnowScraper._cm_to_inches("2.54") - 1.0) < 0.01

    def test_returns_none_for_non_numeric(self):
        assert OnTheSnowScraper._cm_to_inches("abc") is None


class TestOpenFlag:
    """Tests for the open_flag field on ScrapedSnowData."""

    def test_open_flag_default_none(self):
        """Default open_flag is None."""
        data = _make_scraped_data()
        assert data.open_flag is None

    def test_open_flag_can_be_set(self):
        """open_flag can be explicitly set."""
        data = ScrapedSnowData(
            resort_id="test",
            snowfall_24h_inches=None,
            snowfall_48h_inches=None,
            snowfall_72h_inches=None,
            base_depth_inches=None,
            summit_depth_inches=None,
            surface_conditions=None,
            lifts_open=None,
            lifts_total=None,
            runs_open=None,
            runs_total=None,
            last_updated=None,
            source_url="https://test.com",
            open_flag=True,
        )
        assert data.open_flag is True


class TestResortMapping:
    """Tests for the RESORT_URL_MAPPING completeness."""

    def test_mapping_has_na_west_resorts(self):
        """Key NA West resorts are mapped."""
        assert RESORT_URL_MAPPING.get("whistler-blackcomb") is not None
        assert RESORT_URL_MAPPING.get("mammoth-mountain") is not None
        assert RESORT_URL_MAPPING.get("crystal-mountain-wa") is not None
        assert RESORT_URL_MAPPING.get("mt-baker") is not None
        assert RESORT_URL_MAPPING.get("mt-bachelor") is not None
        assert RESORT_URL_MAPPING.get("stevens-pass") is not None

    def test_mapping_has_na_rockies_resorts(self):
        """Key NA Rockies resorts are mapped."""
        assert RESORT_URL_MAPPING.get("vail") is not None
        assert RESORT_URL_MAPPING.get("jackson-hole") is not None
        assert RESORT_URL_MAPPING.get("big-sky-resort") is not None
        assert RESORT_URL_MAPPING.get("alta") is not None
        assert RESORT_URL_MAPPING.get("snowbird") is not None
        assert RESORT_URL_MAPPING.get("deer-valley") is not None
        assert RESORT_URL_MAPPING.get("grand-targhee") is not None
        assert RESORT_URL_MAPPING.get("taos") is not None

    def test_mapping_has_na_east_resorts(self):
        """Key NA East resorts are mapped."""
        assert RESORT_URL_MAPPING.get("stowe") is not None
        assert RESORT_URL_MAPPING.get("killington") is not None
        assert RESORT_URL_MAPPING.get("jay-peak") is not None
        assert RESORT_URL_MAPPING.get("sugarbush") is not None
        assert RESORT_URL_MAPPING.get("sunday-river") is not None
        assert RESORT_URL_MAPPING.get("sugarloaf") is not None

    def test_mapping_has_european_resorts(self):
        """Key Alps resorts are mapped (not None)."""
        assert RESORT_URL_MAPPING.get("chamonix") is not None
        assert RESORT_URL_MAPPING.get("zermatt") is not None
        assert RESORT_URL_MAPPING.get("st-anton") is not None
        assert RESORT_URL_MAPPING.get("verbier") is not None
        assert RESORT_URL_MAPPING.get("val-disere") is not None
        assert RESORT_URL_MAPPING.get("courchevel") is not None
        assert RESORT_URL_MAPPING.get("kitzbuehel") is not None
        assert RESORT_URL_MAPPING.get("cortina") is not None

    def test_japan_oceania_south_america_are_none(self):
        """Japan/Oceania/South America resorts are None (not on OnTheSnow)."""
        assert RESORT_URL_MAPPING.get("niseko") is None
        assert RESORT_URL_MAPPING.get("hakuba") is None
        assert RESORT_URL_MAPPING.get("queenstown-remarkables") is None
        assert RESORT_URL_MAPPING.get("portillo") is None

    def test_url_slugs_have_valid_format(self):
        """All non-None slugs follow region/resort-name pattern."""
        for resort_id, slug in RESORT_URL_MAPPING.items():
            if slug is not None:
                parts = slug.split("/")
                assert len(parts) == 2, (
                    f"{resort_id}: slug '{slug}' should be 'region/resort-name'"
                )
                assert len(parts[0]) > 0, f"{resort_id}: empty region in slug"
                assert len(parts[1]) > 0, f"{resort_id}: empty resort name in slug"

    def test_mapping_count_at_least_60(self):
        """Mapping should have at least 60 active (non-None) entries."""
        active = sum(1 for v in RESORT_URL_MAPPING.values() if v is not None)
        assert active >= 60, f"Only {active} active mappings, expected >= 60"
