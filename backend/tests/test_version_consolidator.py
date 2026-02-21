"""Comprehensive tests for the version_consolidator Lambda handler."""

import io
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import pytest

MODULE = "handlers.version_consolidator"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resort_dict(
    resort_id="whistler",
    name="Whistler Blackcomb",
    country="CA",
    region="na_west",
    latitude=50.1163,
    longitude=-122.9574,
    elevation_base_m=675,
    elevation_top_m=2284,
):
    """Create a resort dict as returned by the scraper."""
    return {
        "resort_id": resort_id,
        "name": name,
        "country": country,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "elevation_base_m": elevation_base_m,
        "elevation_top_m": elevation_top_m,
    }


def _make_production_resort(
    resort_id="whistler",
    name="Whistler Blackcomb",
    country="CA",
    region="na_west",
    elevation_base_m=675,
    elevation_top_m=2284,
    elevation_points=None,
):
    """Create a production resort dict as returned by DynamoDB."""
    data = {
        "resort_id": resort_id,
        "name": name,
        "country": country,
        "region": region,
        "elevation_base_m": elevation_base_m,
        "elevation_top_m": elevation_top_m,
    }
    if elevation_points is not None:
        data["elevation_points"] = elevation_points
    return data


def _make_s3_body(data):
    """Create a mock S3 Body object from a dict."""
    body = io.BytesIO(json.dumps(data).encode("utf-8"))
    return body


def _make_lambda_context():
    """Create a mock Lambda context object."""
    ctx = SimpleNamespace()
    ctx.get_remaining_time_in_millis = lambda: 300000
    return ctx


# ---------------------------------------------------------------------------
# Tests for get_latest_scraper_job_id
# ---------------------------------------------------------------------------


class TestGetLatestScraperJobId:
    """Tests for finding the most recent scraper job ID from S3."""

    @patch(f"{MODULE}.s3")
    def test_returns_latest_job_id(self, mock_s3):
        from handlers.version_consolidator import get_latest_scraper_job_id

        mock_s3.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "scraper-results/20260201060000/"},
                {"Prefix": "scraper-results/20260203060000/"},
                {"Prefix": "scraper-results/20260202060000/"},
            ]
        }

        result = get_latest_scraper_job_id()
        assert result == "20260203060000"

    @patch(f"{MODULE}.s3")
    def test_returns_none_when_no_prefixes(self, mock_s3):
        from handlers.version_consolidator import get_latest_scraper_job_id

        mock_s3.list_objects_v2.return_value = {"CommonPrefixes": []}
        result = get_latest_scraper_job_id()
        assert result is None

    @patch(f"{MODULE}.s3")
    def test_returns_none_when_no_common_prefixes_key(self, mock_s3):
        from handlers.version_consolidator import get_latest_scraper_job_id

        mock_s3.list_objects_v2.return_value = {}
        result = get_latest_scraper_job_id()
        assert result is None

    @patch(f"{MODULE}.s3")
    def test_skips_test_jobs(self, mock_s3):
        from handlers.version_consolidator import get_latest_scraper_job_id

        mock_s3.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "scraper-results/test-run-1/"},
                {"Prefix": "scraper-results/20260201060000/"},
                {"Prefix": "scraper-results/test-run-2/"},
            ]
        }

        result = get_latest_scraper_job_id()
        assert result == "20260201060000"

    @patch(f"{MODULE}.s3")
    def test_returns_none_when_only_test_jobs(self, mock_s3):
        from handlers.version_consolidator import get_latest_scraper_job_id

        mock_s3.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "scraper-results/test-run-1/"},
                {"Prefix": "scraper-results/test-run-2/"},
            ]
        }

        result = get_latest_scraper_job_id()
        assert result is None

    @patch(f"{MODULE}.s3")
    def test_returns_none_on_s3_error(self, mock_s3):
        from handlers.version_consolidator import get_latest_scraper_job_id

        mock_s3.list_objects_v2.side_effect = RuntimeError("S3 connection error")
        result = get_latest_scraper_job_id()
        assert result is None

    @patch(f"{MODULE}.s3")
    def test_filters_empty_job_ids(self, mock_s3):
        """Prefixes that split to empty string should be filtered."""
        from handlers.version_consolidator import get_latest_scraper_job_id

        mock_s3.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "scraper-results//"},  # empty job id
                {"Prefix": "scraper-results/20260201060000/"},
            ]
        }

        result = get_latest_scraper_job_id()
        assert result == "20260201060000"


# ---------------------------------------------------------------------------
# Tests for get_scraper_results
# ---------------------------------------------------------------------------


class TestGetScraperResults:
    """Tests for aggregating scraper results from S3."""

    @patch(f"{MODULE}.s3")
    def test_loads_country_results(self, mock_s3):
        from handlers.version_consolidator import get_scraper_results

        us_data = {
            "resorts": [
                _make_resort_dict("vail", "Vail", "US", "na_rockies"),
                _make_resort_dict("park-city", "Park City", "US", "na_rockies"),
            ],
            "stats": {"resorts_scraped": 2, "resorts_skipped": 0, "errors": 0},
        }
        ca_data = {
            "resorts": [
                _make_resort_dict("whistler", "Whistler", "CA", "na_west"),
            ],
            "stats": {"resorts_scraped": 1, "resorts_skipped": 1, "errors": 0},
        }

        # Mock paginator
        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "scraper-results/job123/US.json"},
                    {"Key": "scraper-results/job123/CA.json"},
                ]
            }
        ]

        mock_s3.get_object.side_effect = [
            {"Body": _make_s3_body(us_data)},
            {"Body": _make_s3_body(ca_data)},
        ]

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 3
        assert "US" in stats_by_country
        assert "CA" in stats_by_country
        assert stats_by_country["US"]["count"] == 2
        assert stats_by_country["US"]["scraped"] == 2
        assert stats_by_country["CA"]["count"] == 1
        assert stats_by_country["CA"]["skipped"] == 1

    @patch(f"{MODULE}.s3")
    def test_skips_metadata_files(self, mock_s3):
        from handlers.version_consolidator import get_scraper_results

        us_data = {
            "resorts": [_make_resort_dict("vail", "Vail", "US")],
            "stats": {"resorts_scraped": 1},
        }

        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "scraper-results/job123/US.json"},
                    {"Key": "scraper-results/job123/US_metadata.json"},
                    {"Key": "scraper-results/job123/job_metadata.json"},
                ]
            }
        ]

        mock_s3.get_object.return_value = {"Body": _make_s3_body(us_data)}

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 1
        # get_object should only be called once (for US.json)
        assert mock_s3.get_object.call_count == 1

    @patch(f"{MODULE}.s3")
    def test_skips_non_json_files(self, mock_s3):
        from handlers.version_consolidator import get_scraper_results

        us_data = {
            "resorts": [_make_resort_dict("vail", "Vail", "US")],
            "stats": {},
        }

        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "scraper-results/job123/US.json"},
                    {"Key": "scraper-results/job123/readme.txt"},
                    {"Key": "scraper-results/job123/log.csv"},
                ]
            }
        ]

        mock_s3.get_object.return_value = {"Body": _make_s3_body(us_data)}

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 1
        assert mock_s3.get_object.call_count == 1

    @patch(f"{MODULE}.s3")
    def test_handles_empty_contents(self, mock_s3):
        from handlers.version_consolidator import get_scraper_results

        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"Contents": []}]

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 0
        assert len(stats_by_country) == 0

    @patch(f"{MODULE}.s3")
    def test_handles_no_contents_key(self, mock_s3):
        from handlers.version_consolidator import get_scraper_results

        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{}]  # no "Contents" key

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 0
        assert len(stats_by_country) == 0

    @patch(f"{MODULE}.s3")
    def test_handles_individual_file_read_error(self, mock_s3):
        """If one file fails to read, others should still be processed."""
        from handlers.version_consolidator import get_scraper_results

        ca_data = {
            "resorts": [_make_resort_dict("whistler", "Whistler", "CA")],
            "stats": {"resorts_scraped": 1},
        }

        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "scraper-results/job123/US.json"},
                    {"Key": "scraper-results/job123/CA.json"},
                ]
            }
        ]

        mock_s3.get_object.side_effect = [
            RuntimeError("S3 read error"),  # US.json fails
            {"Body": _make_s3_body(ca_data)},  # CA.json succeeds
        ]

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 1
        assert resorts[0]["resort_id"] == "whistler"
        assert "CA" in stats_by_country
        assert "US" not in stats_by_country

    @patch(f"{MODULE}.s3")
    def test_handles_paginator_error(self, mock_s3):
        from handlers.version_consolidator import get_scraper_results

        mock_s3.get_paginator.side_effect = RuntimeError("S3 listing error")

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 0
        assert len(stats_by_country) == 0

    @patch(f"{MODULE}.s3")
    def test_multiple_pages(self, mock_s3):
        from handlers.version_consolidator import get_scraper_results

        us_data = {
            "resorts": [_make_resort_dict("vail", "Vail", "US")],
            "stats": {"resorts_scraped": 1},
        }
        ch_data = {
            "resorts": [_make_resort_dict("zermatt", "Zermatt", "CH", "alps")],
            "stats": {"resorts_scraped": 1},
        }

        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "scraper-results/job123/US.json"}]},
            {"Contents": [{"Key": "scraper-results/job123/CH.json"}]},
        ]

        mock_s3.get_object.side_effect = [
            {"Body": _make_s3_body(us_data)},
            {"Body": _make_s3_body(ch_data)},
        ]

        resorts, stats_by_country = get_scraper_results("job123")

        assert len(resorts) == 2
        assert "US" in stats_by_country
        assert "CH" in stats_by_country

    @patch(f"{MODULE}.s3")
    def test_stats_defaults_for_missing_fields(self, mock_s3):
        """Stats fields that are missing from the source should default to 0."""
        from handlers.version_consolidator import get_scraper_results

        data = {
            "resorts": [_make_resort_dict("vail", "Vail", "US")],
            "stats": {},  # empty stats
        }

        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "scraper-results/job123/US.json"}]}
        ]
        mock_s3.get_object.return_value = {"Body": _make_s3_body(data)}

        resorts, stats_by_country = get_scraper_results("job123")

        assert stats_by_country["US"]["scraped"] == 0
        assert stats_by_country["US"]["skipped"] == 0
        assert stats_by_country["US"]["errors"] == 0


# ---------------------------------------------------------------------------
# Tests for get_production_resorts
# ---------------------------------------------------------------------------


class TestGetProductionResorts:
    """Tests for reading production resort data from DynamoDB."""

    @patch(f"{MODULE}.dynamodb")
    def test_returns_resorts_by_id(self, mock_ddb):
        from handlers.version_consolidator import get_production_resorts

        table = MagicMock()
        mock_ddb.Table.return_value = table
        table.scan.return_value = {
            "Items": [
                {"resort_id": "whistler", "name": "Whistler"},
                {"resort_id": "vail", "name": "Vail"},
            ]
        }

        result = get_production_resorts()

        assert len(result) == 2
        assert "whistler" in result
        assert "vail" in result
        assert result["whistler"]["name"] == "Whistler"

    @patch(f"{MODULE}.dynamodb")
    def test_handles_pagination(self, mock_ddb):
        from handlers.version_consolidator import get_production_resorts

        table = MagicMock()
        mock_ddb.Table.return_value = table
        table.scan.side_effect = [
            {
                "Items": [{"resort_id": "whistler", "name": "Whistler"}],
                "LastEvaluatedKey": {"resort_id": "whistler"},
            },
            {
                "Items": [{"resort_id": "vail", "name": "Vail"}],
            },
        ]

        result = get_production_resorts()

        assert len(result) == 2
        assert table.scan.call_count == 2

    @patch(f"{MODULE}.dynamodb")
    def test_handles_empty_table(self, mock_ddb):
        from handlers.version_consolidator import get_production_resorts

        table = MagicMock()
        mock_ddb.Table.return_value = table
        table.scan.return_value = {"Items": []}

        result = get_production_resorts()
        assert len(result) == 0

    @patch(f"{MODULE}.dynamodb")
    def test_skips_items_without_resort_id(self, mock_ddb):
        from handlers.version_consolidator import get_production_resorts

        table = MagicMock()
        mock_ddb.Table.return_value = table
        table.scan.return_value = {
            "Items": [
                {"resort_id": "whistler", "name": "Whistler"},
                {"name": "Unknown"},  # no resort_id
            ]
        }

        result = get_production_resorts()
        assert len(result) == 1
        assert "whistler" in result

    @patch(f"{MODULE}.dynamodb")
    def test_handles_scan_error(self, mock_ddb):
        from handlers.version_consolidator import get_production_resorts

        table = MagicMock()
        mock_ddb.Table.return_value = table
        table.scan.side_effect = RuntimeError("DynamoDB error")

        result = get_production_resorts()
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests for calculate_diff
# ---------------------------------------------------------------------------


class TestCalculateDiff:
    """Tests for diff calculation between new scraper data and production."""

    def test_all_new_resorts(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler", "CA", "na_west"),
            _make_resort_dict("vail", "Vail", "US", "na_rockies"),
        ]
        production_resorts = {}

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["added"]) == 2
        assert len(diff["removed"]) == 0
        assert len(diff["modified"]) == 0
        assert diff["unchanged_count"] == 0

    def test_all_removed_resorts(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = []
        production_resorts = {
            "whistler": _make_production_resort("whistler", "Whistler"),
            "vail": _make_production_resort("vail", "Vail"),
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 2
        assert len(diff["modified"]) == 0

    def test_no_changes(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler", "CA", "na_west"),
        ]
        production_resorts = {
            "whistler": _make_production_resort(
                "whistler",
                "Whistler",
                elevation_base_m=675,
                elevation_top_m=2284,
            ),
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0
        assert len(diff["modified"]) == 0
        assert diff["unchanged_count"] == 1

    def test_modified_name(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler Blackcomb Resort"),
        ]
        production_resorts = {
            "whistler": _make_production_resort("whistler", "Whistler Blackcomb"),
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["modified"]) == 1
        assert diff["modified"][0]["resort_id"] == "whistler"
        assert any("name:" in c for c in diff["modified"][0]["changes"])

    def test_modified_base_elevation(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler", elevation_base_m=700),
        ]
        production_resorts = {
            "whistler": _make_production_resort(
                "whistler", "Whistler", elevation_base_m=675
            ),
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["modified"]) == 1
        assert any("base_elev:" in c for c in diff["modified"][0]["changes"])

    def test_modified_top_elevation(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler", elevation_top_m=2300),
        ]
        production_resorts = {
            "whistler": _make_production_resort(
                "whistler", "Whistler", elevation_top_m=2284
            ),
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["modified"]) == 1
        assert any("top_elev:" in c for c in diff["modified"][0]["changes"])

    def test_elevation_comparison_with_elevation_points_base(self):
        """Production resort using nested elevation_points structure for base."""
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler", elevation_base_m=675),
        ]
        production_resorts = {
            "whistler": {
                "resort_id": "whistler",
                "name": "Whistler",
                "elevation_base_m": None,
                "elevation_top_m": 2284,
                "elevation_points": [
                    {"level": "base", "elevation_meters": 675},
                    {"level": "top", "elevation_meters": 2284},
                ],
            },
        }

        diff = calculate_diff(new_resorts, production_resorts)

        # Base elevation matches through elevation_points fallback
        assert len(diff["modified"]) == 0

    def test_elevation_comparison_with_elevation_points_top(self):
        """Production resort using nested elevation_points structure for top."""
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler", elevation_top_m=2284),
        ]
        production_resorts = {
            "whistler": {
                "resort_id": "whistler",
                "name": "Whistler",
                "elevation_base_m": 675,
                "elevation_top_m": None,
                "elevation_points": [
                    {"level": "base", "elevation_meters": 675},
                    {"level": "top", "elevation_meters": 2284},
                ],
            },
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["modified"]) == 0

    def test_elevation_points_fallback_detects_change(self):
        """When elevation_points has a different value, change should be detected."""
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler", elevation_base_m=700),
        ]
        production_resorts = {
            "whistler": {
                "resort_id": "whistler",
                "name": "Whistler",
                "elevation_base_m": None,
                "elevation_top_m": 2284,
                "elevation_points": [
                    {"level": "base", "elevation_meters": 675},
                    {"level": "top", "elevation_meters": 2284},
                ],
            },
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["modified"]) == 1
        assert any("base_elev:" in c for c in diff["modified"][0]["changes"])

    def test_mixed_add_remove_modify(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("whistler", "Whistler Updated"),  # modified
            _make_resort_dict("zermatt", "Zermatt", "CH", "alps"),  # added
        ]
        production_resorts = {
            "whistler": _make_production_resort("whistler", "Whistler"),
            "vail": _make_production_resort(
                "vail", "Vail", "US", "na_rockies"
            ),  # removed
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["added"]) == 1
        assert diff["added"][0]["resort_id"] == "zermatt"
        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["resort_id"] == "vail"
        assert len(diff["modified"]) == 1
        assert diff["modified"][0]["resort_id"] == "whistler"
        assert diff["unchanged_count"] == 0

    def test_added_resorts_sorted_by_id(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict("zermatt", "Zermatt"),
            _make_resort_dict("aspen", "Aspen"),
            _make_resort_dict("mammoth", "Mammoth"),
        ]
        production_resorts = {}

        diff = calculate_diff(new_resorts, production_resorts)

        ids = [r["resort_id"] for r in diff["added"]]
        assert ids == sorted(ids)

    def test_removed_resorts_sorted_by_id(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = []
        production_resorts = {
            "zermatt": _make_production_resort("zermatt", "Zermatt"),
            "aspen": _make_production_resort("aspen", "Aspen"),
            "mammoth": _make_production_resort("mammoth", "Mammoth"),
        }

        diff = calculate_diff(new_resorts, production_resorts)

        ids = [r["resort_id"] for r in diff["removed"]]
        assert ids == sorted(ids)

    def test_multiple_changes_on_one_resort(self):
        from handlers.version_consolidator import calculate_diff

        new_resorts = [
            _make_resort_dict(
                "whistler",
                "Whistler Updated",
                elevation_base_m=700,
                elevation_top_m=2300,
            ),
        ]
        production_resorts = {
            "whistler": _make_production_resort(
                "whistler",
                "Whistler",
                elevation_base_m=675,
                elevation_top_m=2284,
            ),
        }

        diff = calculate_diff(new_resorts, production_resorts)

        assert len(diff["modified"]) == 1
        changes = diff["modified"][0]["changes"]
        assert len(changes) == 3  # name, base_elev, top_elev


# ---------------------------------------------------------------------------
# Tests for generate_stats
# ---------------------------------------------------------------------------


class TestGenerateStats:
    """Tests for resort dataset statistics generation."""

    def test_basic_stats(self):
        from handlers.version_consolidator import generate_stats

        resorts = [
            _make_resort_dict("whistler", "Whistler", "CA", "na_west"),
            _make_resort_dict("vail", "Vail", "US", "na_rockies"),
            _make_resort_dict("park-city", "Park City", "US", "na_rockies"),
        ]
        stats_by_country = {
            "CA": {"count": 1, "scraped": 1, "skipped": 0, "errors": 0},
            "US": {"count": 2, "scraped": 2, "skipped": 0, "errors": 0},
        }

        stats = generate_stats(resorts, stats_by_country)

        assert stats["total_resorts"] == 3
        assert stats["by_country"]["CA"] == 1
        assert stats["by_country"]["US"] == 2
        assert stats["by_region"]["na_west"] == 1
        assert stats["by_region"]["na_rockies"] == 2
        assert stats["scraper_stats"] == stats_by_country

    def test_with_valid_coordinates(self):
        from handlers.version_consolidator import generate_stats

        resorts = [
            _make_resort_dict("whistler", latitude=50.1, longitude=-122.9),
            _make_resort_dict("vail", latitude=39.6, longitude=-106.4),
            {
                "resort_id": "unknown",
                "name": "Unknown",
                "country": "XX",
                "region": "xx",
                "latitude": 0,
                "longitude": 0,
            },
        ]

        stats = generate_stats(resorts, {})

        assert stats["with_valid_coordinates"] == 2

    def test_empty_resorts(self):
        from handlers.version_consolidator import generate_stats

        stats = generate_stats([], {})

        assert stats["total_resorts"] == 0
        assert stats["by_country"] == {}
        assert stats["by_region"] == {}
        assert stats["with_valid_coordinates"] == 0

    def test_unknown_country_and_region(self):
        from handlers.version_consolidator import generate_stats

        resorts = [
            {"resort_id": "x", "name": "X"},  # no country/region keys
        ]

        stats = generate_stats(resorts, {})

        assert stats["by_country"]["unknown"] == 1
        assert stats["by_region"]["unknown"] == 1

    def test_coordinates_with_nonzero_latitude_only(self):
        """A resort with latitude != 0 but longitude == 0 counts as valid."""
        from handlers.version_consolidator import generate_stats

        resorts = [
            {
                "resort_id": "eq",
                "name": "Equator",
                "country": "XX",
                "region": "xx",
                "latitude": 1.0,
                "longitude": 0,
            },
        ]

        stats = generate_stats(resorts, {})

        assert stats["with_valid_coordinates"] == 1

    def test_coordinates_with_nonzero_longitude_only(self):
        """A resort with longitude != 0 but latitude == 0 counts as valid."""
        from handlers.version_consolidator import generate_stats

        resorts = [
            {
                "resort_id": "eq",
                "name": "Meridian",
                "country": "XX",
                "region": "xx",
                "latitude": 0,
                "longitude": 1.0,
            },
        ]

        stats = generate_stats(resorts, {})

        assert stats["with_valid_coordinates"] == 1


# ---------------------------------------------------------------------------
# Tests for store_version
# ---------------------------------------------------------------------------


class TestStoreVersion:
    """Tests for storing consolidated data and manifest to S3."""

    @patch(f"{MODULE}.s3")
    def test_stores_data_and_manifest(self, mock_s3):
        from handlers.version_consolidator import store_version

        resorts = [_make_resort_dict("whistler")]
        manifest = {"version_id": "v20260203060000", "stats": {}}

        data_key, manifest_key = store_version("20260203060000", resorts, manifest)

        assert data_key == "resort-versions/data/v20260203060000/resorts.json"
        assert manifest_key == "resort-versions/manifests/v20260203060000.json"
        assert mock_s3.put_object.call_count == 2

    @patch(f"{MODULE}.s3")
    def test_data_key_format(self, mock_s3):
        from handlers.version_consolidator import store_version

        store_version("job123", [], {})

        # First call is data, second is manifest
        data_call = mock_s3.put_object.call_args_list[0]
        assert data_call[1]["Key"] == "resort-versions/data/vjob123/resorts.json"
        assert data_call[1]["ContentType"] == "application/json"

    @patch(f"{MODULE}.s3")
    def test_manifest_key_format(self, mock_s3):
        from handlers.version_consolidator import store_version

        store_version("job123", [], {})

        manifest_call = mock_s3.put_object.call_args_list[1]
        assert manifest_call[1]["Key"] == "resort-versions/manifests/vjob123.json"
        assert manifest_call[1]["ContentType"] == "application/json"

    @patch(f"{MODULE}.s3")
    def test_data_body_contains_resorts(self, mock_s3):
        from handlers.version_consolidator import store_version

        resorts = [_make_resort_dict("whistler"), _make_resort_dict("vail")]
        store_version("job123", resorts, {})

        data_call = mock_s3.put_object.call_args_list[0]
        body = json.loads(data_call[1]["Body"])
        assert len(body["resorts"]) == 2

    @patch(f"{MODULE}.s3")
    def test_manifest_body_is_stored(self, mock_s3):
        from handlers.version_consolidator import store_version

        manifest = {"version_id": "vjob123", "status": "pending"}
        store_version("job123", [], manifest)

        manifest_call = mock_s3.put_object.call_args_list[1]
        body = json.loads(manifest_call[1]["Body"])
        assert body["version_id"] == "vjob123"
        assert body["status"] == "pending"


# ---------------------------------------------------------------------------
# Tests for send_notification
# ---------------------------------------------------------------------------


class TestSendNotification:
    """Tests for SNS notification sending."""

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "arn:aws:sns:us-west-2:123:topic")
    @patch(f"{MODULE}.sns")
    def test_sends_notification(self, mock_sns):
        from handlers.version_consolidator import send_notification

        stats = {"total_resorts": 100}
        diff = {
            "added": [{"name": "New Resort", "country": "US"}],
            "removed": [],
            "modified": [{"resort_id": "x", "changes": ["name"]}],
        }

        send_notification("v20260203060000", stats, diff)

        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args[1]
        assert call_kwargs["TopicArn"] == "arn:aws:sns:us-west-2:123:topic"
        assert "v20260203060000" in call_kwargs["Subject"]
        assert "+1/-0" in call_kwargs["Subject"]

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "")
    @patch(f"{MODULE}.sns")
    def test_skips_when_no_topic_arn(self, mock_sns):
        from handlers.version_consolidator import send_notification

        send_notification("v123", {}, {"added": [], "removed": [], "modified": []})

        mock_sns.publish.assert_not_called()

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "arn:aws:sns:us-west-2:123:topic")
    @patch(f"{MODULE}.sns")
    def test_handles_publish_error(self, mock_sns):
        from handlers.version_consolidator import send_notification

        mock_sns.publish.side_effect = RuntimeError("SNS error")
        stats = {"total_resorts": 50}
        diff = {"added": [], "removed": [], "modified": []}

        # Should not raise
        send_notification("v123", stats, diff)

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "arn:aws:sns:us-west-2:123:topic")
    @patch(f"{MODULE}.sns")
    def test_message_contains_added_resorts(self, mock_sns):
        from handlers.version_consolidator import send_notification

        stats = {"total_resorts": 10}
        diff = {
            "added": [
                {"name": "Resort A", "country": "US"},
                {"name": "Resort B", "country": "CA"},
            ],
            "removed": [],
            "modified": [],
        }

        send_notification("v123", stats, diff)

        message = mock_sns.publish.call_args[1]["Message"]
        assert "Resort A" in message
        assert "Resort B" in message
        assert "ADDED RESORTS" in message

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "arn:aws:sns:us-west-2:123:topic")
    @patch(f"{MODULE}.sns")
    def test_message_contains_removed_resorts(self, mock_sns):
        from handlers.version_consolidator import send_notification

        stats = {"total_resorts": 10}
        diff = {
            "added": [],
            "removed": [
                {"name": "Old Resort", "country": "CH"},
            ],
            "modified": [],
        }

        send_notification("v123", stats, diff)

        message = mock_sns.publish.call_args[1]["Message"]
        assert "Old Resort" in message
        assert "REMOVED RESORTS" in message

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "arn:aws:sns:us-west-2:123:topic")
    @patch(f"{MODULE}.sns")
    def test_message_truncates_long_lists(self, mock_sns):
        from handlers.version_consolidator import send_notification

        stats = {"total_resorts": 30}
        added = [{"name": f"Resort {i}", "country": "US"} for i in range(25)]
        diff = {"added": added, "removed": [], "modified": []}

        send_notification("v123", stats, diff)

        message = mock_sns.publish.call_args[1]["Message"]
        assert "... and 5 more" in message

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "arn:aws:sns:us-west-2:123:topic")
    @patch(f"{MODULE}.sns")
    def test_subject_truncated_to_100_chars(self, mock_sns):
        from handlers.version_consolidator import send_notification

        stats = {"total_resorts": 10}
        diff = {"added": [], "removed": [], "modified": []}

        send_notification("v123", stats, diff)

        subject = mock_sns.publish.call_args[1]["Subject"]
        assert len(subject) <= 100

    @patch(f"{MODULE}.RESORT_UPDATES_TOPIC_ARN", "arn:aws:sns:us-west-2:123:topic")
    @patch(f"{MODULE}.sns")
    def test_message_contains_deploy_instructions(self, mock_sns):
        from handlers.version_consolidator import send_notification

        stats = {"total_resorts": 10}
        diff = {"added": [], "removed": [], "modified": []}

        send_notification("v123", stats, diff)

        message = mock_sns.publish.call_args[1]["Message"]
        assert "To deploy this version:" in message
        assert "gh workflow run" in message


# ---------------------------------------------------------------------------
# Tests for version_consolidator_handler (Lambda entry point)
# ---------------------------------------------------------------------------


class TestVersionConsolidatorHandler:
    """Tests for the main Lambda handler function."""

    @patch(f"{MODULE}.send_notification")
    @patch(f"{MODULE}.store_version")
    @patch(f"{MODULE}.get_production_resorts")
    @patch(f"{MODULE}.get_scraper_results")
    def test_success_with_explicit_job_id(
        self, mock_get_results, mock_get_prod, mock_store, mock_notify
    ):
        from handlers.version_consolidator import version_consolidator_handler

        resorts = [
            _make_resort_dict("whistler", "Whistler", "CA", "na_west"),
            _make_resort_dict("vail", "Vail", "US", "na_rockies"),
        ]
        mock_get_results.return_value = (
            resorts,
            {"CA": {"count": 1}, "US": {"count": 1}},
        )
        mock_get_prod.return_value = {}
        mock_store.return_value = (
            "resort-versions/data/vjob123/resorts.json",
            "resort-versions/manifests/vjob123.json",
        )

        result = version_consolidator_handler(
            {"job_id": "job123"}, _make_lambda_context()
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version_id"] == "vjob123"
        assert body["total_resorts"] == 2
        assert body["added"] == 2
        assert body["removed"] == 0
        mock_store.assert_called_once()
        mock_notify.assert_called_once()

    @patch(f"{MODULE}.send_notification")
    @patch(f"{MODULE}.store_version")
    @patch(f"{MODULE}.get_production_resorts")
    @patch(f"{MODULE}.get_scraper_results")
    @patch(f"{MODULE}.get_latest_scraper_job_id")
    def test_success_with_latest_job(
        self, mock_get_latest, mock_get_results, mock_get_prod, mock_store, mock_notify
    ):
        from handlers.version_consolidator import version_consolidator_handler

        mock_get_latest.return_value = "20260203060000"
        resorts = [_make_resort_dict("whistler")]
        mock_get_results.return_value = (resorts, {"CA": {"count": 1}})
        mock_get_prod.return_value = {}
        mock_store.return_value = ("data_key", "manifest_key")

        result = version_consolidator_handler({}, _make_lambda_context())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["version_id"] == "v20260203060000"
        mock_get_latest.assert_called_once()

    @patch(f"{MODULE}.get_latest_scraper_job_id")
    def test_no_job_id_and_no_latest(self, mock_get_latest):
        from handlers.version_consolidator import version_consolidator_handler

        mock_get_latest.return_value = None

        result = version_consolidator_handler({}, _make_lambda_context())

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "error" in body

    @patch(f"{MODULE}.get_scraper_results")
    def test_no_resorts_found(self, mock_get_results):
        from handlers.version_consolidator import version_consolidator_handler

        mock_get_results.return_value = ([], {})

        result = version_consolidator_handler(
            {"job_id": "job123"}, _make_lambda_context()
        )

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert "No resorts found" in body["error"]

    @patch(f"{MODULE}.get_latest_scraper_job_id")
    def test_no_job_id_with_process_latest_false(self, mock_get_latest):
        from handlers.version_consolidator import version_consolidator_handler

        result = version_consolidator_handler(
            {"process_latest": False}, _make_lambda_context()
        )

        assert result["statusCode"] == 400
        mock_get_latest.assert_not_called()

    @patch(f"{MODULE}.send_notification")
    @patch(f"{MODULE}.store_version")
    @patch(f"{MODULE}.get_production_resorts")
    @patch(f"{MODULE}.get_scraper_results")
    def test_response_includes_duration(
        self, mock_get_results, mock_get_prod, mock_store, mock_notify
    ):
        from handlers.version_consolidator import version_consolidator_handler

        resorts = [_make_resort_dict("whistler")]
        mock_get_results.return_value = (resorts, {})
        mock_get_prod.return_value = {}
        mock_store.return_value = ("data_key", "manifest_key")

        result = version_consolidator_handler(
            {"job_id": "job123"}, _make_lambda_context()
        )

        body = json.loads(result["body"])
        assert "duration_seconds" in body
        assert body["duration_seconds"] >= 0

    @patch(f"{MODULE}.send_notification")
    @patch(f"{MODULE}.store_version")
    @patch(f"{MODULE}.get_production_resorts")
    @patch(f"{MODULE}.get_scraper_results")
    def test_manifest_structure(
        self, mock_get_results, mock_get_prod, mock_store, mock_notify
    ):
        from handlers.version_consolidator import version_consolidator_handler

        resorts = [_make_resort_dict("whistler")]
        mock_get_results.return_value = (resorts, {"CA": {"count": 1}})
        mock_get_prod.return_value = {
            "vail": _make_production_resort("vail", "Vail"),
        }
        mock_store.return_value = ("data_key", "manifest_key")

        version_consolidator_handler({"job_id": "job123"}, _make_lambda_context())

        # Verify manifest passed to store_version
        call_args = mock_store.call_args
        manifest = call_args[0][2]  # third positional arg

        assert manifest["version_id"] == "vjob123"
        assert manifest["job_id"] == "job123"
        assert manifest["status"] == "pending"
        assert manifest["deployment_history"] == []
        assert "created_at" in manifest
        assert "stats" in manifest
        assert "diff" in manifest
        assert manifest["stats"]["total_resorts"] == 1

    @patch(f"{MODULE}.send_notification")
    @patch(f"{MODULE}.store_version")
    @patch(f"{MODULE}.get_production_resorts")
    @patch(f"{MODULE}.get_scraper_results")
    def test_diff_passed_to_notification(
        self, mock_get_results, mock_get_prod, mock_store, mock_notify
    ):
        from handlers.version_consolidator import version_consolidator_handler

        resorts = [_make_resort_dict("whistler")]
        mock_get_results.return_value = (resorts, {})
        mock_get_prod.return_value = {}
        mock_store.return_value = ("data_key", "manifest_key")

        version_consolidator_handler({"job_id": "job123"}, _make_lambda_context())

        # Verify notification was called with version_id, stats, and diff
        notify_args = mock_notify.call_args[0]
        assert notify_args[0] == "vjob123"  # version_id
        assert notify_args[1]["total_resorts"] == 1  # stats
        assert len(notify_args[2]["added"]) == 1  # diff

    @patch(f"{MODULE}.send_notification")
    @patch(f"{MODULE}.store_version")
    @patch(f"{MODULE}.get_production_resorts")
    @patch(f"{MODULE}.get_scraper_results")
    def test_response_body_fields(
        self, mock_get_results, mock_get_prod, mock_store, mock_notify
    ):
        from handlers.version_consolidator import version_consolidator_handler

        new_resorts = [
            _make_resort_dict("whistler", "Whistler"),
            _make_resort_dict("zermatt", "Zermatt", "CH", "alps"),
        ]
        mock_get_results.return_value = (new_resorts, {})
        mock_get_prod.return_value = {
            "whistler": _make_production_resort("whistler", "Whistler Updated"),
            "vail": _make_production_resort("vail", "Vail"),
        }
        mock_store.return_value = ("data_key", "manifest_key")

        result = version_consolidator_handler(
            {"job_id": "job123"}, _make_lambda_context()
        )

        body = json.loads(result["body"])
        assert body["message"] == "Created version vjob123"
        assert body["version_id"] == "vjob123"
        assert body["total_resorts"] == 2
        assert body["added"] == 1  # zermatt
        assert body["removed"] == 1  # vail
        assert body["modified"] == 1  # whistler (name change)
        assert body["data_key"] == "data_key"
        assert body["manifest_key"] == "manifest_key"

    @patch(f"{MODULE}.send_notification")
    @patch(f"{MODULE}.store_version")
    @patch(f"{MODULE}.get_production_resorts")
    @patch(f"{MODULE}.get_scraper_results")
    def test_environment_in_manifest(
        self, mock_get_results, mock_get_prod, mock_store, mock_notify
    ):
        from handlers.version_consolidator import version_consolidator_handler

        resorts = [_make_resort_dict("whistler")]
        mock_get_results.return_value = (resorts, {})
        mock_get_prod.return_value = {}
        mock_store.return_value = ("data_key", "manifest_key")

        with patch(f"{MODULE}.ENVIRONMENT", "staging"):
            version_consolidator_handler({"job_id": "job123"}, _make_lambda_context())

        manifest = mock_store.call_args[0][2]
        assert manifest["environment"] == "staging"
