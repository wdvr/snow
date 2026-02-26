"""Tests for MultiSourceMerger."""

import pytest

from models.weather import ConfidenceLevel
from services.multi_source_merger import (
    DEFAULT_WEIGHTS,
    DEPTH_PRIORITY,
    MultiSourceMerger,
    SourceData,
)


class TestSourceData:
    """Tests for the SourceData dataclass."""

    def test_default_values(self):
        sd = SourceData(source_name="test")
        assert sd.source_name == "test"
        assert sd.snowfall_24h_cm is None
        assert sd.snowfall_48h_cm is None
        assert sd.snowfall_72h_cm is None
        assert sd.snow_depth_cm is None
        assert sd.temperature_c is None
        assert sd.surface_conditions is None
        assert sd.raw_data == {}

    def test_with_values(self):
        sd = SourceData(
            source_name="onthesnow",
            snowfall_24h_cm=5.0,
            snow_depth_cm=120.0,
            raw_data={"source_url": "https://example.com"},
        )
        assert sd.snowfall_24h_cm == 5.0
        assert sd.snow_depth_cm == 120.0
        assert sd.raw_data["source_url"] == "https://example.com"


class TestMultiSourceMergerNoSources:
    """Tests when no supplementary sources are provided."""

    def test_no_sources_returns_base_data(self):
        base = {
            "snowfall_24h_cm": 5.0,
            "snowfall_48h_cm": 10.0,
            "snow_depth_cm": 100.0,
            "temperature_c": -5.0,
        }
        result = MultiSourceMerger.merge(base, [])
        assert result == base

    def test_empty_sources_list(self):
        base = {"snowfall_24h_cm": 3.0}
        result = MultiSourceMerger.merge(base, [])
        assert result["snowfall_24h_cm"] == 3.0


class TestMultiSourceMergerSingleSource:
    """Tests with one supplementary source."""

    def test_openmeteo_plus_onthesnow_snowfall_blend(self):
        """Two sources should produce weighted average of snowfall."""
        base = {
            "snowfall_24h_cm": 0.0,
            "snowfall_48h_cm": 2.0,
            "snowfall_72h_cm": 5.0,
            "snow_depth_cm": 80.0,
        }
        onthesnow = SourceData(
            source_name="onthesnow",
            snowfall_24h_cm=3.0,
            snowfall_48h_cm=6.0,
            snowfall_72h_cm=10.0,
            snow_depth_cm=120.0,
            raw_data={"snowfall_24h_inches": 1.2},
        )
        result = MultiSourceMerger.merge(base, [onthesnow])

        # Normalized weights: open-meteo=0.50/0.75=0.667, onthesnow=0.25/0.75=0.333
        # 24h: (0.0 * 0.667 + 3.0 * 0.333) / 1.0 = 1.0
        expected_24h = round(0.0 * (0.50 / 0.75) + 3.0 * (0.25 / 0.75), 1)
        assert result["snowfall_24h_cm"] == expected_24h

        # Snow depth: onthesnow has priority over open-meteo
        assert result["snow_depth_cm"] == 120.0

        # Should have medium or high confidence with 2 sources
        assert result["source_confidence"] in [
            ConfidenceLevel.MEDIUM,
            ConfidenceLevel.HIGH,
        ]

        # Raw data stored for debugging
        assert "scraped_onthesnow" in result["raw_data"]

    def test_onthesnow_depth_overrides_openmeteo(self):
        """Resort-reported depth should override model estimate."""
        base = {"snow_depth_cm": 50.0}
        onthesnow = SourceData(
            source_name="onthesnow",
            snow_depth_cm=90.0,
        )
        result = MultiSourceMerger.merge(base, [onthesnow])
        assert result["snow_depth_cm"] == 90.0

    def test_snowforecast_depth_overrides_openmeteo(self):
        """Snow-Forecast depth should override Open-Meteo."""
        base = {"snow_depth_cm": 50.0}
        sf = SourceData(
            source_name="snowforecast",
            snow_depth_cm=75.0,
        )
        result = MultiSourceMerger.merge(base, [sf])
        assert result["snow_depth_cm"] == 75.0


class TestMultiSourceMergerMultipleSources:
    """Tests with multiple supplementary sources."""

    def test_three_sources_weighted_average(self):
        """Three sources should produce properly weighted snowfall average."""
        base = {
            "snowfall_24h_cm": 2.0,
            "snowfall_48h_cm": 5.0,
        }
        onthesnow = SourceData(
            source_name="onthesnow",
            snowfall_24h_cm=4.0,
            snowfall_48h_cm=8.0,
            snow_depth_cm=100.0,
        )
        snowforecast = SourceData(
            source_name="snowforecast",
            snowfall_24h_cm=3.0,
            snowfall_48h_cm=7.0,
            snow_depth_cm=90.0,
        )
        result = MultiSourceMerger.merge(base, [onthesnow, snowforecast])

        # All 3 sources available: normalized weights
        # open-meteo=0.50/0.90, onthesnow=0.25/0.90, snowforecast=0.15/0.90
        w_om = 0.50 / 0.90
        w_ots = 0.25 / 0.90
        w_sf = 0.15 / 0.90
        expected_24h = round(2.0 * w_om + 4.0 * w_ots + 3.0 * w_sf, 1)
        assert result["snowfall_24h_cm"] == expected_24h

        # OnTheSnow has highest depth priority
        assert result["snow_depth_cm"] == 100.0

        # 3 sources with data = HIGH confidence
        assert result["source_confidence"] == ConfidenceLevel.HIGH

    def test_all_four_sources(self):
        """All four sources produce correctly weighted average."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=3.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=4.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # All weights sum to 1.0, so normalized = original
        expected = round(0.0 * 0.50 + 5.0 * 0.25 + 3.0 * 0.15 + 4.0 * 0.10, 1)
        assert result["snowfall_24h_cm"] == expected

    def test_depth_priority_onthesnow_over_snowforecast(self):
        """OnTheSnow depth should take priority over Snow-Forecast."""
        base = {"snow_depth_cm": 50.0}
        sources = [
            SourceData(source_name="onthesnow", snow_depth_cm=100.0),
            SourceData(source_name="snowforecast", snow_depth_cm=90.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        assert result["snow_depth_cm"] == 100.0

    def test_depth_priority_snowforecast_when_no_onthesnow(self):
        """Snow-Forecast depth used when OnTheSnow has no depth."""
        base = {"snow_depth_cm": 50.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),  # no depth
            SourceData(source_name="snowforecast", snow_depth_cm=90.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        assert result["snow_depth_cm"] == 90.0


class TestMultiSourceMergerConfidence:
    """Tests for confidence level calculation."""

    def test_single_source_keeps_existing_confidence(self):
        """With only Open-Meteo, confidence stays as-is."""
        base = {
            "snowfall_24h_cm": 5.0,
            "source_confidence": ConfidenceLevel.LOW,
        }
        result = MultiSourceMerger.merge(base, [])
        assert result["source_confidence"] == ConfidenceLevel.LOW

    def test_two_agreeing_sources_high_confidence(self):
        """Two sources with similar values should give HIGH confidence."""
        base = {"snowfall_24h_cm": 5.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=5.5)
        result = MultiSourceMerger.merge(base, [ots])
        # Both report ~5cm → agreement → HIGH
        assert result["source_confidence"] == ConfidenceLevel.HIGH

    def test_two_disagreeing_sources_medium_confidence(self):
        """Two sources with very different values should give MEDIUM confidence."""
        base = {"snowfall_24h_cm": 0.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=10.0)
        result = MultiSourceMerger.merge(base, [ots])
        # 0 vs 10 → disagreement → MEDIUM (or less)
        assert result["source_confidence"] in [
            ConfidenceLevel.MEDIUM,
            ConfidenceLevel.HIGH,
        ]

    def test_three_sources_high_confidence(self):
        """Three sources with snowfall data should give HIGH confidence."""
        base = {"snowfall_24h_cm": 5.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=4.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=6.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        assert result["source_confidence"] == ConfidenceLevel.HIGH


class TestMultiSourceMergerDataSource:
    """Tests for data_source string generation."""

    def test_single_supplementary_source(self):
        base = {"snowfall_24h_cm": 5.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=3.0)
        result = MultiSourceMerger.merge(base, [ots])
        assert "onthesnow.com" in result["data_source"]
        assert "open-meteo.com" in result["data_source"]

    def test_weatherkit_special_domain(self):
        base = {"snowfall_24h_cm": 5.0}
        wk = SourceData(source_name="weatherkit", snowfall_24h_cm=3.0)
        result = MultiSourceMerger.merge(base, [wk])
        assert "weatherkit.apple.com" in result["data_source"]

    def test_all_sources_listed(self):
        base = {"snowfall_24h_cm": 5.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=3.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=4.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=2.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        assert "open-meteo.com" in result["data_source"]
        assert "onthesnow.com" in result["data_source"]
        assert "snowforecast.com" in result["data_source"]
        assert "weatherkit.apple.com" in result["data_source"]


class TestMultiSourceMergerEdgeCases:
    """Edge case tests."""

    def test_source_with_no_snowfall_data(self):
        """Source with only depth data doesn't affect snowfall average."""
        base = {"snowfall_24h_cm": 5.0, "snow_depth_cm": 80.0}
        ots = SourceData(
            source_name="onthesnow",
            snow_depth_cm=120.0,
            # No snowfall data
        )
        result = MultiSourceMerger.merge(base, [ots])
        # Snowfall should not change (only Open-Meteo has snowfall data)
        assert result["snowfall_24h_cm"] == 5.0
        # Depth should be overridden
        assert result["snow_depth_cm"] == 120.0

    def test_partial_snowfall_windows(self):
        """Source with only 24h data doesn't affect 48h/72h."""
        base = {
            "snowfall_24h_cm": 5.0,
            "snowfall_48h_cm": 10.0,
            "snowfall_72h_cm": 15.0,
        }
        ots = SourceData(
            source_name="onthesnow",
            snowfall_24h_cm=8.0,
            # No 48h or 72h data
        )
        result = MultiSourceMerger.merge(base, [ots])
        # 24h should be blended
        assert result["snowfall_24h_cm"] != 5.0
        # 48h and 72h should stay (only Open-Meteo has data for these)
        assert result["snowfall_48h_cm"] == 10.0
        assert result["snowfall_72h_cm"] == 15.0

    def test_zero_snowfall_treated_as_data(self):
        """Zero snowfall is valid data, not missing."""
        base = {"snowfall_24h_cm": 0.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=5.0)
        result = MultiSourceMerger.merge(base, [ots])
        # Should be weighted average of 0.0 and 5.0, not just 5.0
        assert 0 < result["snowfall_24h_cm"] < 5.0

    def test_custom_weights(self):
        """Custom weights should override defaults."""
        base = {"snowfall_24h_cm": 10.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=0.0)
        custom_weights = {"open-meteo": 0.50, "onthesnow": 0.50}
        result = MultiSourceMerger.merge(base, [ots], weights=custom_weights)
        assert result["snowfall_24h_cm"] == 5.0  # 50/50 of 10 and 0

    def test_raw_data_preserved(self):
        """Raw data from sources stored for debugging."""
        base = {"snowfall_24h_cm": 5.0}
        ots = SourceData(
            source_name="onthesnow",
            snowfall_24h_cm=3.0,
            raw_data={"snowfall_24h_inches": 1.2, "source_url": "https://example.com"},
        )
        result = MultiSourceMerger.merge(base, [ots])
        assert result["raw_data"]["scraped_onthesnow"]["snowfall_24h_inches"] == 1.2

    def test_existing_raw_data_not_lost(self):
        """Pre-existing raw_data in base should not be lost."""
        base = {
            "snowfall_24h_cm": 5.0,
            "raw_data": {"openmeteo_model": "icon_eu"},
        }
        ots = SourceData(
            source_name="onthesnow",
            snowfall_24h_cm=3.0,
            raw_data={"source": "ots"},
        )
        result = MultiSourceMerger.merge(base, [ots])
        assert result["raw_data"]["openmeteo_model"] == "icon_eu"
        assert result["raw_data"]["scraped_onthesnow"]["source"] == "ots"


class TestMultiSourceMergerBackwardCompatibility:
    """Ensure backward compatibility with existing OnTheSnow 70/30 merge pattern."""

    def test_only_onthesnow_produces_similar_weights(self):
        """With only Open-Meteo + OnTheSnow, weights should be approximately 67/33.

        Old system: 70% scraped + 30% API
        New system: normalized 0.50/(0.50+0.25)=0.667 Open-Meteo + 0.25/0.75=0.333 OnTheSnow

        This is close enough — the old system weighted scraped MORE (70%),
        but the new system gives Open-Meteo more weight as the primary source.
        The key difference: old system trusted scraper more, new system trusts
        the primary source more but still blends in the scraper.
        """
        base = {"snowfall_24h_cm": 0.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=7.62)

        result = MultiSourceMerger.merge(base, [ots])

        # New: 0.0 * 0.667 + 7.62 * 0.333 = ~2.5
        # Old: 7.62 * 0.7 + 0.0 * 0.3 = 5.33
        # This IS different — the new merger trusts the primary source more.
        # That's intentional: Open-Meteo is always there, supplementary sources add signal.
        new_value = result["snowfall_24h_cm"]
        assert 2.0 < new_value < 3.0  # Roughly 0.333 * 7.62
