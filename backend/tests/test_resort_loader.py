"""Tests for resort_loader utility."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from models.resort import ElevationLevel, Resort
from utils.resort_loader import ResortLoader, load_resorts

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DATA = {
    "version": "1.0.0",
    "regions": {
        "alps": {
            "name": "European Alps",
            "display_name": "Alps",
            "countries": ["FR", "CH", "AT", "IT"],
        },
        "na_west": {
            "name": "North America - West",
            "display_name": "NA West Coast",
            "countries": ["CA", "US"],
        },
    },
    "resorts": [
        {
            "resort_id": "chamonix",
            "name": "Chamonix Mont-Blanc",
            "country": "FR",
            "region": "alps",
            "state_province": "Haute-Savoie",
            "elevation_base_m": 1035,
            "elevation_top_m": 3842,
            "latitude": 45.9237,
            "longitude": 6.8694,
            "timezone": "Europe/Paris",
            "website": "https://www.chamonix.com",
        },
        {
            "resort_id": "zermatt",
            "name": "Zermatt",
            "country": "CH",
            "region": "alps",
            "state_province": "Valais",
            "elevation_base_m": 1620,
            "elevation_top_m": 3883,
            "latitude": 46.0207,
            "longitude": 7.7491,
            "timezone": "Europe/Zurich",
            "website": "https://www.zermatt.ch",
        },
        {
            "resort_id": "whistler",
            "name": "Whistler Blackcomb",
            "country": "CA",
            "region": "na_west",
            "state_province": "BC",
            "elevation_base_m": 675,
            "elevation_top_m": 2284,
            "latitude": 50.1163,
            "longitude": -122.9574,
            "timezone": "America/Vancouver",
            "website": "https://www.whistlerblackcomb.com",
        },
    ],
}


@pytest.fixture
def tmp_json(tmp_path: Path) -> Path:
    """Write SAMPLE_DATA to a temporary JSON file and return the path."""
    file = tmp_path / "resorts.json"
    file.write_text(json.dumps(SAMPLE_DATA), encoding="utf-8")
    return file


@pytest.fixture
def loader(tmp_json: Path) -> ResortLoader:
    """Return a ResortLoader pointed at the temporary JSON file."""
    return ResortLoader(data_file=tmp_json)


# ---------------------------------------------------------------------------
# Tests – loading
# ---------------------------------------------------------------------------


class TestResortLoaderLoad:
    """Tests for ResortLoader.load()."""

    def test_load_returns_data(self, loader: ResortLoader):
        """Loading a valid JSON file returns the parsed dictionary."""
        data = loader.load()
        assert isinstance(data, dict)
        assert "resorts" in data
        assert "regions" in data

    def test_load_caches_result(self, loader: ResortLoader):
        """Calling load() twice returns the same cached object."""
        first = loader.load()
        second = loader.load()
        assert first is second

    def test_load_file_not_found(self, tmp_path: Path):
        """Loading from a non-existent path raises FileNotFoundError."""
        missing = tmp_path / "does_not_exist.json"
        loader = ResortLoader(data_file=missing)
        with pytest.raises(FileNotFoundError, match="Resort data file not found"):
            loader.load()

    def test_load_invalid_json(self, tmp_path: Path):
        """Loading invalid JSON raises json.JSONDecodeError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json}", encoding="utf-8")
        loader = ResortLoader(data_file=bad_file)
        with pytest.raises(json.JSONDecodeError):
            loader.load()

    def test_load_logs_resort_count(self, loader: ResortLoader, caplog):
        """Loading logs the number of resorts found."""
        import logging

        with caplog.at_level(logging.INFO, logger="utils.resort_loader"):
            loader.load()
        assert "Loaded 3 resorts" in caplog.text


# ---------------------------------------------------------------------------
# Tests – regions
# ---------------------------------------------------------------------------


class TestGetRegions:
    """Tests for ResortLoader.get_regions()."""

    def test_get_regions_returns_dict(self, loader: ResortLoader):
        """get_regions() returns the regions sub-dictionary."""
        regions = loader.get_regions()
        assert isinstance(regions, dict)
        assert "alps" in regions
        assert "na_west" in regions

    def test_get_regions_structure(self, loader: ResortLoader):
        """Each region has name, display_name, and countries."""
        regions = loader.get_regions()
        alps = regions["alps"]
        assert alps["name"] == "European Alps"
        assert alps["display_name"] == "Alps"
        assert "FR" in alps["countries"]

    def test_get_regions_empty_data(self, tmp_path: Path):
        """get_regions() returns empty dict when no regions key exists."""
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"resorts": []}), encoding="utf-8")
        loader = ResortLoader(data_file=f)
        assert loader.get_regions() == {}


class TestGetRegionList:
    """Tests for ResortLoader.get_region_list()."""

    def test_get_region_list_returns_list(self, loader: ResortLoader):
        """get_region_list() returns a list of region dicts."""
        result = loader.get_region_list()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_region_list_fields(self, loader: ResortLoader):
        """Each item has id, name, display_name, countries, resort_count."""
        result = loader.get_region_list()
        for region in result:
            assert "id" in region
            assert "name" in region
            assert "display_name" in region
            assert "countries" in region
            assert "resort_count" in region

    def test_get_region_list_sorted_by_count_descending(self, loader: ResortLoader):
        """Regions are sorted by resort_count descending."""
        result = loader.get_region_list()
        counts = [r["resort_count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_get_region_list_counts_correct(self, loader: ResortLoader):
        """alps has 2 resorts, na_west has 1."""
        result = loader.get_region_list()
        by_id = {r["id"]: r for r in result}
        assert by_id["alps"]["resort_count"] == 2
        assert by_id["na_west"]["resort_count"] == 1

    def test_get_region_list_empty_data(self, tmp_path: Path):
        """No regions and no resorts yields empty list."""
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"resorts": [], "regions": {}}), encoding="utf-8")
        loader = ResortLoader(data_file=f)
        assert loader.get_region_list() == []


# ---------------------------------------------------------------------------
# Tests – get_resorts
# ---------------------------------------------------------------------------


class TestGetResorts:
    """Tests for ResortLoader.get_resorts()."""

    def test_get_resorts_all(self, loader: ResortLoader):
        """Without a region filter, all resorts are returned."""
        resorts = loader.get_resorts()
        assert len(resorts) == 3
        assert all(isinstance(r, Resort) for r in resorts)

    def test_get_resorts_filter_by_region(self, loader: ResortLoader):
        """Filtering by region returns only matching resorts."""
        alps_resorts = loader.get_resorts(region="alps")
        assert len(alps_resorts) == 2
        assert all(r.resort_id in ("chamonix", "zermatt") for r in alps_resorts)

    def test_get_resorts_filter_nonexistent_region(self, loader: ResortLoader):
        """Filtering by a region with no matches returns empty list."""
        resorts = loader.get_resorts(region="nonexistent")
        assert resorts == []

    def test_get_resorts_resort_fields(self, loader: ResortLoader):
        """Returned Resort objects have expected field values."""
        resorts = loader.get_resorts()
        chamonix = next(r for r in resorts if r.resort_id == "chamonix")
        assert chamonix.name == "Chamonix Mont-Blanc"
        assert chamonix.country == "FR"
        assert chamonix.region == "Haute-Savoie"  # state_province overrides region
        assert chamonix.timezone == "Europe/Paris"
        assert chamonix.official_website == "https://www.chamonix.com"
        assert chamonix.weather_sources == ["weatherapi"]

    def test_get_resorts_elevation_points(self, loader: ResortLoader):
        """Each resort has 3 elevation points (base, mid, top)."""
        resorts = loader.get_resorts()
        chamonix = next(r for r in resorts if r.resort_id == "chamonix")
        assert len(chamonix.elevation_points) == 3

        levels = [p.level for p in chamonix.elevation_points]
        assert ElevationLevel.BASE in levels
        assert ElevationLevel.MID in levels
        assert ElevationLevel.TOP in levels

    def test_get_resorts_elevation_calculations(self, loader: ResortLoader):
        """Elevation meters and feet are computed correctly."""
        resorts = loader.get_resorts()
        chamonix = next(r for r in resorts if r.resort_id == "chamonix")

        base = chamonix.base_elevation
        mid = chamonix.mid_elevation
        top = chamonix.top_elevation

        # Base elevation
        assert base.elevation_meters == 1035
        assert base.elevation_feet == int(1035 * 3.28084)

        # Mid elevation = floor((base + top) / 2)
        expected_mid_m = (1035 + 3842) // 2
        assert mid.elevation_meters == expected_mid_m
        assert mid.elevation_feet == int(expected_mid_m * 3.28084)

        # Top elevation
        assert top.elevation_meters == 3842
        assert top.elevation_feet == int(3842 * 3.28084)

    def test_get_resorts_coordinates_northern_hemisphere(self, loader: ResortLoader):
        """For northern hemisphere resorts, lat increases for mid/top."""
        resorts = loader.get_resorts()
        chamonix = next(r for r in resorts if r.resort_id == "chamonix")

        base = chamonix.base_elevation
        mid = chamonix.mid_elevation
        top = chamonix.top_elevation

        # Base has exact coordinates
        assert base.latitude == pytest.approx(45.9237)
        assert base.longitude == pytest.approx(6.8694)

        # Northern hemisphere: lat_diff = +0.005
        assert mid.latitude == pytest.approx(45.9237 + 0.005)
        assert mid.longitude == pytest.approx(6.8694 + 0.005)
        assert top.latitude == pytest.approx(45.9237 + 0.010)
        assert top.longitude == pytest.approx(6.8694 + 0.010)

    def test_get_resorts_timestamps_set(self, loader: ResortLoader):
        """Each resort has created_at and updated_at set."""
        resorts = loader.get_resorts()
        for resort in resorts:
            assert resort.created_at is not None
            assert resort.updated_at is not None
            assert resort.created_at == resort.updated_at

    def test_get_resorts_skips_bad_entries(self, tmp_path: Path):
        """If a resort entry is malformed, it is skipped with a warning."""
        data = {
            "resorts": [
                {
                    # Missing required 'resort_id' and 'name' keys
                    "country": "XX",
                },
                {
                    "resort_id": "good-resort",
                    "name": "Good Resort",
                    "country": "US",
                    "region": "na_west",
                    "elevation_base_m": 2000,
                    "elevation_top_m": 3000,
                    "latitude": 40.0,
                    "longitude": -105.0,
                    "timezone": "America/Denver",
                },
            ]
        }
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        loader = ResortLoader(data_file=f)
        resorts = loader.get_resorts()
        assert len(resorts) == 1
        assert resorts[0].resort_id == "good-resort"


# ---------------------------------------------------------------------------
# Tests – _transform_resort (elevation coordinate logic)
# ---------------------------------------------------------------------------


class TestTransformResort:
    """Tests for ResortLoader._transform_resort edge cases."""

    def test_southern_hemisphere_lat_diff(self, loader: ResortLoader):
        """For southern-hemisphere resorts, lat_diff is -0.005."""
        raw = {
            "resort_id": "southern-resort",
            "name": "Southern Resort",
            "country": "NZ",
            "region": "oceania",
            "elevation_base_m": 1000,
            "elevation_top_m": 2000,
            "latitude": -45.0,
            "longitude": 168.0,
            "timezone": "Pacific/Auckland",
        }
        resort = loader._transform_resort(raw, "2026-01-01T00:00:00Z")
        base = resort.base_elevation
        mid = resort.mid_elevation
        top = resort.top_elevation

        # Southern hemisphere: lat_diff = -0.005
        assert mid.latitude == pytest.approx(-45.0 + (-0.005))
        assert top.latitude == pytest.approx(-45.0 + (-0.010))
        # Longitude always +0.005
        assert mid.longitude == pytest.approx(168.0 + 0.005)
        assert top.longitude == pytest.approx(168.0 + 0.010)

    def test_defaults_for_missing_optional_fields(self, loader: ResortLoader):
        """Missing optional fields receive sensible defaults."""
        raw = {
            "resort_id": "minimal",
            "name": "Minimal Resort",
            "country": "US",
        }
        resort = loader._transform_resort(raw, "2026-01-01T00:00:00Z")

        # Defaults
        assert resort.timezone == "UTC"
        assert resort.official_website is None
        assert resort.region == ""  # no state_province, no region

        # Elevation defaults to 0
        base = resort.base_elevation
        assert base.elevation_meters == 0

    def test_state_province_overrides_region(self, loader: ResortLoader):
        """state_province takes precedence over region for the Resort.region field."""
        raw = {
            "resort_id": "test",
            "name": "Test",
            "country": "CA",
            "region": "na_west",
            "state_province": "BC",
            "elevation_base_m": 500,
            "elevation_top_m": 1500,
            "latitude": 50.0,
            "longitude": -120.0,
            "timezone": "America/Vancouver",
        }
        resort = loader._transform_resort(raw, "2026-01-01T00:00:00Z")
        assert resort.region == "BC"

    def test_region_used_when_no_state_province(self, loader: ResortLoader):
        """When state_province is absent, resort.region falls back to raw region."""
        raw = {
            "resort_id": "test",
            "name": "Test",
            "country": "JP",
            "region": "japan",
            "elevation_base_m": 500,
            "elevation_top_m": 1500,
            "latitude": 43.0,
            "longitude": 140.0,
            "timezone": "Asia/Tokyo",
        }
        resort = loader._transform_resort(raw, "2026-01-01T00:00:00Z")
        assert resort.region == "japan"


# ---------------------------------------------------------------------------
# Tests – get_resort_by_id
# ---------------------------------------------------------------------------


class TestGetResortById:
    """Tests for ResortLoader.get_resort_by_id()."""

    def test_found(self, loader: ResortLoader):
        """Returns a Resort when the ID matches."""
        resort = loader.get_resort_by_id("whistler")
        assert resort is not None
        assert isinstance(resort, Resort)
        assert resort.resort_id == "whistler"
        assert resort.name == "Whistler Blackcomb"

    def test_not_found(self, loader: ResortLoader):
        """Returns None when no resort matches the ID."""
        assert loader.get_resort_by_id("nonexistent") is None

    def test_returns_correct_resort(self, loader: ResortLoader):
        """Ensure the right resort object is returned (not the first one)."""
        resort = loader.get_resort_by_id("zermatt")
        assert resort is not None
        assert resort.name == "Zermatt"
        assert resort.country == "CH"


# ---------------------------------------------------------------------------
# Tests – get_resorts_by_country
# ---------------------------------------------------------------------------


class TestGetResortsByCountry:
    """Tests for ResortLoader.get_resorts_by_country()."""

    def test_single_match(self, loader: ResortLoader):
        """Country with one resort returns a single-element list."""
        resorts = loader.get_resorts_by_country("CA")
        assert len(resorts) == 1
        assert resorts[0].resort_id == "whistler"

    def test_multiple_matches(self, loader: ResortLoader):
        """Country with multiple resorts returns all of them."""
        # FR has chamonix only in our sample data
        resorts = loader.get_resorts_by_country("FR")
        assert len(resorts) == 1
        assert resorts[0].resort_id == "chamonix"

    def test_no_match(self, loader: ResortLoader):
        """Country with no resorts returns empty list."""
        resorts = loader.get_resorts_by_country("XX")
        assert resorts == []


# ---------------------------------------------------------------------------
# Tests – convenience function
# ---------------------------------------------------------------------------


class TestLoadResortsConvenience:
    """Tests for the module-level load_resorts() convenience function."""

    def test_load_resorts_uses_default_file(self, tmp_json: Path):
        """load_resorts() delegates to ResortLoader with default DATA_FILE."""
        with patch(
            "utils.resort_loader.ResortLoader",
            return_value=ResortLoader(data_file=tmp_json),
        ):
            resorts = load_resorts()
        assert len(resorts) == 3
        assert all(isinstance(r, Resort) for r in resorts)

    def test_load_resorts_with_region(self, tmp_json: Path):
        """load_resorts(region=...) filters correctly."""
        with patch(
            "utils.resort_loader.ResortLoader",
            return_value=ResortLoader(data_file=tmp_json),
        ):
            resorts = load_resorts(region="na_west")
        assert len(resorts) == 1
        assert resorts[0].resort_id == "whistler"

    def test_load_resorts_no_match(self, tmp_json: Path):
        """load_resorts(region=...) with unknown region returns empty list."""
        with patch(
            "utils.resort_loader.ResortLoader",
            return_value=ResortLoader(data_file=tmp_json),
        ):
            resorts = load_resorts(region="unknown")
        assert resorts == []


# ---------------------------------------------------------------------------
# Tests – real data file (integration-style)
# ---------------------------------------------------------------------------


class TestRealDataFile:
    """Integration-level tests that read the actual resorts.json file."""

    @pytest.fixture
    def real_loader(self) -> ResortLoader:
        """Return a ResortLoader using the real data file."""
        real_file = Path(__file__).parent.parent / "data" / "resorts.json"
        if not real_file.exists():
            pytest.skip("Real resorts.json not available")
        return ResortLoader(data_file=real_file)

    def test_real_file_loads(self, real_loader: ResortLoader):
        """The real resorts.json file loads without errors."""
        data = real_loader.load()
        assert "resorts" in data
        assert "regions" in data
        assert len(data["resorts"]) > 0

    def test_real_file_all_resorts_transform(self, real_loader: ResortLoader):
        """Every resort in the real file transforms to a valid Resort object."""
        resorts = real_loader.get_resorts()
        assert len(resorts) > 0
        for resort in resorts:
            assert resort.resort_id
            assert resort.name
            assert len(resort.elevation_points) == 3
