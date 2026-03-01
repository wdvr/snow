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
        """Two sources with >50% disagreement → outlier detection picks higher value."""
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

        # Two sources disagree (0 vs 3, >50% diff) → outlier detection, higher value trusted
        assert result["snowfall_24h_cm"] == 3.0

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

    def test_three_sources_consensus_average(self):
        """Three agreeing sources produce simple average (no outliers)."""
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

        # All 3 within 50% of median → consensus → simple average
        assert result["snowfall_24h_cm"] == round((2.0 + 4.0 + 3.0) / 3, 1)
        assert result["snowfall_48h_cm"] == round((5.0 + 8.0 + 7.0) / 3, 1)

        # OnTheSnow has highest depth priority
        assert result["snow_depth_cm"] == 100.0

        # 3 agreeing sources = HIGH confidence
        assert result["source_confidence"] == ConfidenceLevel.HIGH

    def test_all_four_sources_outlier_dropped(self):
        """Open-Meteo outlier (0cm) dropped when 3 others report snow."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=3.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=4.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # Open-Meteo=0 is outlier (>50% from median 3.5)
        # Consensus: {5, 3, 4} → avg = 4.0
        assert result["snowfall_24h_cm"] == 4.0

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
        # 0 vs 10 → outlier detection (>50% diff) → MEDIUM
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
        """Zero snowfall is valid data, not missing. With >50% diff, outlier detection picks higher."""
        base = {"snowfall_24h_cm": 0.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=5.0)
        result = MultiSourceMerger.merge(base, [ots])
        # Two sources disagree by 100% → outlier detection, higher value trusted
        assert result["snowfall_24h_cm"] == 5.0

    def test_custom_weights(self):
        """Custom weights used in weighted average for moderate disagreement (30-50%)."""
        base = {"snowfall_24h_cm": 10.0}
        # 10 vs 6 = 40% difference → falls in 30-50% weighted average zone
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=6.0)
        custom_weights = {"open-meteo": 0.50, "onthesnow": 0.50}
        result = MultiSourceMerger.merge(base, [ots], weights=custom_weights)
        # Disagree by 40% → weighted avg: 50/50 of 10 and 6 = 8.0
        assert result["snowfall_24h_cm"] == 8.0

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


class TestMultiSourceMergerTwoSourceFallback:
    """Test behavior when only 2 sources disagree (weighted average fallback)."""

    def test_two_disagreeing_sources_outlier_detection(self):
        """With only Open-Meteo + OnTheSnow disagreeing by >50%, outlier detection picks higher."""
        base = {"snowfall_24h_cm": 0.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=7.62)

        result = MultiSourceMerger.merge(base, [ots])

        # 0 vs 7.62 = 100% diff → outlier detection, higher value trusted
        assert result["snowfall_24h_cm"] == 7.6  # rounded to 1 decimal

    def test_two_agreeing_sources_simple_average(self):
        """Two sources within 30% → simple average (no weighted fallback)."""
        base = {"snowfall_24h_cm": 5.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=5.5)

        result = MultiSourceMerger.merge(base, [ots])

        # Within 30% → simple average
        assert result["snowfall_24h_cm"] == round((5.0 + 5.5) / 2, 1)

    def test_two_sources_moderate_disagreement_weighted_average(self):
        """Two sources with 30-50% disagreement → weighted average (gray zone)."""
        base = {"snowfall_24h_cm": 10.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=6.0)

        result = MultiSourceMerger.merge(base, [ots])

        # 40% difference → weighted average zone
        assert result["source_details"]["merge_method"] == "weighted_average"
        # Both sources should be "included" (not outlier, not consensus)
        for src_info in result["source_details"]["sources"].values():
            if src_info.get("snowfall_24h_cm") is not None:
                assert src_info["status"] == "included"


class TestTwoSourceOutlierDetection:
    """BUG-011: Tests for outlier detection in the 2-source case."""

    def test_extreme_disagreement_outlier_detection(self):
        """Two sources with >50% disagreement → outlier detection, lower value marked outlier."""
        base = {"snowfall_24h_cm": 0.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=10.0)

        result = MultiSourceMerger.merge(base, [ots])

        # 100% difference → outlier detection, higher value (10.0) trusted
        assert result["snowfall_24h_cm"] == 10.0
        sd = result["source_details"]
        assert sd["merge_method"] == "outlier_detection"
        assert sd["sources"]["open-meteo.com"]["status"] == "outlier"
        assert sd["sources"]["onthesnow.com"]["status"] == "consensus"

    def test_moderate_disagreement_weighted_average(self):
        """Two sources with 30-50% disagreement → weighted average, not outlier detection."""
        base = {"snowfall_24h_cm": 10.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=6.5)

        result = MultiSourceMerger.merge(base, [ots])

        # 35% difference → weighted average (gray zone)
        sd = result["source_details"]
        assert sd["merge_method"] == "weighted_average"
        # Both sources should be "included"
        assert sd["sources"]["open-meteo.com"]["status"] == "included"
        assert sd["sources"]["onthesnow.com"]["status"] == "included"

    def test_within_threshold_consensus(self):
        """Two sources within 30% → consensus (simple average), unchanged behavior."""
        base = {"snowfall_24h_cm": 10.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=8.0)

        result = MultiSourceMerger.merge(base, [ots])

        # 20% difference → simple average
        assert result["snowfall_24h_cm"] == round((10.0 + 8.0) / 2, 1)
        sd = result["source_details"]
        assert sd["merge_method"] == "simple_average"
        assert sd["sources"]["open-meteo.com"]["status"] == "consensus"
        assert sd["sources"]["onthesnow.com"]["status"] == "consensus"

    def test_both_near_zero_consensus(self):
        """Both sources near zero (<1.0) → consensus regardless of percentage difference."""
        base = {"snowfall_24h_cm": 0.1}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=0.8)

        result = MultiSourceMerger.merge(base, [ots])

        # Both < 1.0 → near zero, simple average
        assert result["snowfall_24h_cm"] == round((0.1 + 0.8) / 2, 1)
        sd = result["source_details"]
        assert sd["merge_method"] == "simple_average"

    def test_97_percent_disagreement_triggers_outlier(self):
        """97% disagreement should trigger outlier detection, not weighted average."""
        base = {"snowfall_24h_cm": 0.5}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=15.0)

        result = MultiSourceMerger.merge(base, [ots])

        # 97% difference → outlier detection, higher value trusted
        assert result["snowfall_24h_cm"] == 15.0
        sd = result["source_details"]
        assert sd["merge_method"] == "outlier_detection"
        assert sd["sources"]["open-meteo.com"]["status"] == "outlier"
        assert sd["sources"]["onthesnow.com"]["status"] == "consensus"

    def test_higher_value_always_trusted_for_snowfall(self):
        """Higher source is trusted because stations under-report snow more often."""
        base = {"snowfall_24h_cm": 2.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=20.0)

        result = MultiSourceMerger.merge(base, [ots])

        # open-meteo=2 is outlier (90% diff), onthesnow=20 is trusted
        assert result["snowfall_24h_cm"] == 20.0
        sd = result["source_details"]
        assert sd["sources"]["open-meteo.com"]["status"] == "outlier"
        assert sd["sources"]["onthesnow.com"]["status"] == "consensus"


class TestMultiSourceMergerOutlierDetection:
    """Tests for the outlier detection + majority consensus algorithm."""

    def test_big_white_scenario(self):
        """The motivating case: Open-Meteo misses snow that scrapers catch.

        Open-Meteo=0cm, OnTheSnow=3cm, Snow-Forecast=3cm → should be 3.0cm
        (not 1.3cm as with old weighted average).
        """
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=3.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=3.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # Open-Meteo=0 is outlier, consensus={3,3} → avg=3.0
        assert result["snowfall_24h_cm"] == 3.0

    def test_high_outlier_dropped(self):
        """One source reports much higher than others → dropped."""
        base = {"snowfall_24h_cm": 5.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=15.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # SF=15 is outlier (>50% from median 5), consensus={5,5} → avg=5.0
        assert result["snowfall_24h_cm"] == 5.0

    def test_all_zeros_consensus(self):
        """All sources report zero → consensus on zero."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=0.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=0.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        assert result["snowfall_24h_cm"] == 0.0

    def test_near_zero_majority_wins(self):
        """Two sources say zero, one says snow → majority wins (zero)."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=0.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=3.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # Median=0, absolute threshold: 0 and 0 ≤ 1.0 (consensus), 3 > 1.0 (outlier)
        assert result["snowfall_24h_cm"] == 0.0

    def test_all_agree_no_outlier(self):
        """All sources similar → average all."""
        base = {"snowfall_24h_cm": 4.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=4.5),
            SourceData(source_name="weatherkit", snowfall_24h_cm=4.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # All within 50% of median → consensus → avg
        assert result["snowfall_24h_cm"] == round((4.0 + 5.0 + 4.5 + 4.0) / 4, 1)

    def test_no_consensus_weighted_fallback(self):
        """All values wildly different → weighted average fallback."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=10.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=30.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # {0, 10, 30}: median=10, only {10} in consensus → weighted avg fallback
        assert result["snowfall_24h_cm"] > 0

    def test_outlier_detection_confidence_medium(self):
        """When outlier is detected, confidence should be MEDIUM."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=4.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # Open-Meteo=0 disagrees with scrapers → MEDIUM
        assert result["source_confidence"] == ConfidenceLevel.MEDIUM


class TestSourceDetails:
    """Tests for source_details transparency in merged output."""

    def test_no_source_details_without_supplementary_sources(self):
        """Empty sources list returns no source_details."""
        base = {"snowfall_24h_cm": 5.0, "snowfall_48h_cm": 10.0}
        result = MultiSourceMerger.merge(base, [])
        assert "source_details" not in result

    def test_source_details_present_with_sources(self):
        """source_details present when supplementary sources exist."""
        base = {"snowfall_24h_cm": 5.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=5.5)
        result = MultiSourceMerger.merge(base, [ots])
        assert "source_details" in result
        assert "sources" in result["source_details"]
        assert "merge_method" in result["source_details"]
        assert "consensus_value_cm" in result["source_details"]
        assert "source_count" in result["source_details"]

    def test_source_details_correct_domain_names(self):
        """Sources use domain name format (not internal names)."""
        base = {"snowfall_24h_cm": 5.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=4.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=6.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=5.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        sd = result["source_details"]["sources"]
        assert "open-meteo.com" in sd
        assert "onthesnow.com" in sd
        assert "snow-forecast.com" in sd
        assert "weatherkit.apple.com" in sd
        # Internal names should NOT appear
        assert "open-meteo" not in sd
        assert "onthesnow" not in sd
        assert "snowforecast" not in sd
        assert "weatherkit" not in sd

    def test_source_details_outlier_detected(self):
        """Open-Meteo 0cm with 3 others reporting snow → open-meteo.com is outlier."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=3.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=3.2),
            SourceData(source_name="weatherkit", snowfall_24h_cm=2.8),
        ]
        result = MultiSourceMerger.merge(base, sources)
        sd = result["source_details"]
        assert sd["merge_method"] == "outlier_detection"
        assert sd["sources"]["open-meteo.com"]["status"] == "outlier"
        assert sd["sources"]["onthesnow.com"]["status"] == "consensus"
        assert sd["sources"]["snow-forecast.com"]["status"] == "consensus"
        assert sd["sources"]["weatherkit.apple.com"]["status"] == "consensus"

    def test_source_details_all_consensus(self):
        """All sources agree → all status 'consensus'."""
        base = {"snowfall_24h_cm": 4.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=4.5),
            SourceData(source_name="weatherkit", snowfall_24h_cm=4.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        sd = result["source_details"]
        for domain_info in sd["sources"].values():
            assert domain_info["status"] == "consensus"

    def test_source_details_merge_method_outlier_detection_two_sources(self):
        """2 sources disagreeing >50% → merge_method is 'outlier_detection'."""
        base = {"snowfall_24h_cm": 0.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=10.0)
        result = MultiSourceMerger.merge(base, [ots])
        assert result["source_details"]["merge_method"] == "outlier_detection"

    def test_source_details_merge_method_weighted_average(self):
        """2 sources disagreeing 30-50% → merge_method is 'weighted_average'."""
        base = {"snowfall_24h_cm": 10.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=6.0)
        result = MultiSourceMerger.merge(base, [ots])
        assert result["source_details"]["merge_method"] == "weighted_average"

    def test_source_details_merge_method_simple_average(self):
        """2 agreeing sources → merge_method is 'simple_average'."""
        base = {"snowfall_24h_cm": 5.0}
        ots = SourceData(source_name="onthesnow", snowfall_24h_cm=5.5)
        result = MultiSourceMerger.merge(base, [ots])
        assert result["source_details"]["merge_method"] == "simple_average"

    def test_source_details_source_count(self):
        """source_count reflects total available sources."""
        base = {"snowfall_24h_cm": 5.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=4.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=6.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        # 3 sources total: open-meteo + onthesnow + snowforecast
        assert result["source_details"]["source_count"] == 3

    def test_source_details_when_supplementary_has_no_snowfall(self):
        """source_details present even when scrapers report only depth, not snowfall."""
        base = {"snowfall_24h_cm": 0.1, "snow_depth_cm": 50.0}
        sources = [
            SourceData(source_name="onthesnow", snow_depth_cm=120.0),
            SourceData(source_name="snowforecast", snow_depth_cm=110.0),
        ]
        result = MultiSourceMerger.merge(base, sources)
        sd = result["source_details"]
        assert sd["source_count"] == 3
        assert sd["merge_method"] == "single_source"
        # Open-Meteo has snowfall data, others don't
        assert sd["sources"]["open-meteo.com"]["snowfall_24h_cm"] == 0.1
        assert sd["sources"]["onthesnow.com"]["snowfall_24h_cm"] is None
        assert sd["sources"]["snow-forecast.com"]["snowfall_24h_cm"] is None


class TestResortPrioritySnowfall:
    """Tests for resort-reported snowfall priority over weather models.

    When weather models (Open-Meteo, WeatherKit) report near-zero snowfall
    but resort-reported sources (OnTheSnow) report significant snow (≥5cm),
    the resort data should be trusted. Weather models use ~9km grid cells
    and systematically miss terrain-driven mountain snow.
    """

    def test_lake_louise_scenario(self):
        """The motivating bug: OnTheSnow=14cm excluded as outlier when models say near-zero.

        Before fix: median=0.6 < 1.0, OnTheSnow 14cm > 1cm → excluded → result 0.3cm
        After fix: OnTheSnow 14cm ≥ 5cm threshold → resort priority → result 14.0cm
        """
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=14.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=0.6),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # Resort reports 14cm → trusted over models
        assert result["snowfall_24h_cm"] == 14.0
        sd = result["source_details"]
        assert sd["merge_method"] == "resort_priority"
        assert sd["sources"]["onthesnow.com"]["status"] == "consensus"
        assert sd["sources"]["open-meteo.com"]["status"] == "outlier"
        assert sd["sources"]["weatherkit.apple.com"]["status"] == "outlier"

    def test_resort_priority_models_all_zero(self):
        """3 sources: OM=0, WK=0, OTS=10 → resort priority trusts OnTheSnow."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=10.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=0.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # median=0 < 1.0, OTS=10 ≥ 5cm → resort priority
        assert result["snowfall_24h_cm"] == 10.0
        sd = result["source_details"]
        assert sd["merge_method"] == "resort_priority"
        assert sd["sources"]["onthesnow.com"]["status"] == "consensus"
        assert sd["sources"]["open-meteo.com"]["status"] == "outlier"
        assert sd["sources"]["weatherkit.apple.com"]["status"] == "outlier"

    def test_below_threshold_still_excluded(self):
        """Resort source with < 5cm in near-zero case → standard near-zero logic applies."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=3.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=0.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # OnTheSnow=3cm < 5cm threshold → standard near-zero → excluded
        assert result["snowfall_24h_cm"] == 0.0

    def test_near_zero_majority_still_works(self):
        """Two sources at zero + one resort at small value → majority wins (unchanged)."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=0.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=3.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # OM=0, OTS=0, SF=3: median=0, SF=3 < 5cm → standard near-zero
        # Consensus={OM=0, OTS=0}, SF excluded
        assert result["snowfall_24h_cm"] == 0.0

    def test_resort_priority_reason_strings(self):
        """Verify transparency: reasons explain why resort data was trusted."""
        base = {"snowfall_24h_cm": 0.2}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=12.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=0.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        sd = result["source_details"]
        assert "resort-measured" in sd["sources"]["onthesnow.com"]["reason"]
        assert "underreported" in sd["sources"]["open-meteo.com"]["reason"]

    def test_exactly_at_threshold(self):
        """Resort source at exactly 5cm → should trigger resort priority."""
        base = {"snowfall_24h_cm": 0.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="weatherkit", snowfall_24h_cm=0.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        assert result["snowfall_24h_cm"] == 5.0
        assert result["source_details"]["merge_method"] == "resort_priority"

    def test_standard_case_unaffected(self):
        """When median ≥ 1.0, resort priority doesn't apply (standard outlier detection)."""
        base = {"snowfall_24h_cm": 5.0}
        sources = [
            SourceData(source_name="onthesnow", snowfall_24h_cm=5.0),
            SourceData(source_name="snowforecast", snowfall_24h_cm=15.0),
        ]
        result = MultiSourceMerger.merge(base, sources)

        # Median=5.0 ≥ 1.0 → standard outlier detection
        # SF=15 is outlier (>50% from median 5)
        assert result["snowfall_24h_cm"] == 5.0
        assert result["source_details"]["merge_method"] == "outlier_detection"
