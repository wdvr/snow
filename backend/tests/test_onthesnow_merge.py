"""Tests for OnTheSnow scraper merge_with_weather_data snow_depth integration.

Regression: The scraper was scraping base_depth and summit_depth from OnTheSnow
but only storing them in raw_data (debug info). The snow_depth_cm field was never
updated, so Open-Meteo's grid-level model depth (often 0cm for mountain resorts)
was used instead. Combined with the scraper upgrading source_confidence to HIGH,
this made snow_depth_reliable=True with depth=0, triggering the HORRIBLE floor
for resorts that actually have plenty of snow (e.g., Palisades Tahoe 28" base,
Vail 65" base, Steamboat 57" base).

Fix: merge_with_weather_data() now promotes scraped base_depth/summit_depth
to the snow_depth_cm field based on the elevation level being processed.
"""

from services.onthesnow_scraper import OnTheSnowScraper, ScrapedSnowData


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
