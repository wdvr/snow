"""Season dates on the resort payloads (API endpoints and static resorts.json)."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from models.resort import ElevationLevel, ElevationPoint, Resort
from services import season_dates
from utils.cache import clear_all_caches

ENTRIES = {
    "kirkwood": {
        "opening_date": "2099-12-04",
        "closing_date": "2100-04-11",
        "open_flag": 2,
        "fetched_at": "2026-11-17T00:00:00+00:00",
    }
}


def _resort(resort_id: str) -> Resort:
    return Resort(
        resort_id=resort_id,
        name=resort_id.title(),
        country="US",
        region="CA",
        timezone="America/Los_Angeles",
        elevation_points=[
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=2377,
                elevation_feet=7800,
                latitude=38.68,
                longitude=-120.07,
            )
        ],
    )


@pytest.fixture(autouse=True)
def _reset():
    clear_all_caches()
    season_dates.clear_cache()
    yield
    clear_all_caches()
    season_dates.clear_cache()


@pytest.fixture()
def client():
    from handlers.api_handler import app, reset_services

    reset_services()
    return TestClient(app)


@pytest.fixture()
def with_entries():
    with patch("handlers.api_handler.load_season_dates", return_value=ENTRIES):
        yield


class TestResortList:
    @patch("handlers.api_handler._get_static_resorts_from_s3")
    def test_list_includes_season_fields(self, mock_static, client, with_entries):
        mock_static.return_value = [
            _resort("kirkwood").model_dump(),
            _resort("homewood").model_dump(),
        ]
        resp = client.get("/api/v1/resorts")
        assert resp.status_code == 200
        by_id = {r["resort_id"]: r for r in resp.json()["resorts"]}
        assert by_id["kirkwood"]["opening_date"] == "2099-12-04"
        assert by_id["kirkwood"]["closing_date"] == "2100-04-11"
        assert by_id["kirkwood"]["season_status"] == "pre_season"
        assert by_id["kirkwood"]["season_dates_source"] == "onthesnow"
        # No source data: fields present but null
        assert by_id["homewood"]["opening_date"] is None
        assert by_id["homewood"]["season_status"] is None

    @patch("handlers.api_handler._get_static_resorts_from_s3")
    def test_list_without_season_cache_keeps_static_values(self, mock_static, client):
        static = _resort("kirkwood").model_dump()
        static.update(opening_date="2099-12-04", season_status="pre_season")
        mock_static.return_value = [static]
        with patch("handlers.api_handler.load_season_dates", return_value={}):
            resp = client.get("/api/v1/resorts")
        r = resp.json()["resorts"][0]
        assert r["opening_date"] == "2099-12-04"
        assert r["season_status"] == "pre_season"

    @patch("handlers.api_handler._get_static_resorts_from_s3")
    def test_season_cache_failure_does_not_break_list(self, mock_static, client):
        mock_static.return_value = [_resort("kirkwood").model_dump()]
        with patch(
            "handlers.api_handler.load_season_dates", side_effect=RuntimeError("s3")
        ):
            resp = client.get("/api/v1/resorts")
        assert resp.status_code == 200
        assert resp.json()["resorts"][0]["opening_date"] is None

    @patch("handlers.api_handler._get_static_resorts_from_s3", return_value=None)
    @patch("handlers.api_handler.get_resort_service")
    def test_dynamodb_fallback_gets_dates(
        self, mock_svc, _static, client, with_entries
    ):
        svc = MagicMock()
        svc.get_all_resorts.return_value = [_resort("kirkwood")]
        mock_svc.return_value = svc
        resp = client.get("/api/v1/resorts")
        assert resp.json()["resorts"][0]["opening_date"] == "2099-12-04"

    @patch("handlers.api_handler._get_static_resorts_from_s3")
    def test_sorting_still_works_with_season_fields(
        self, mock_static, client, with_entries
    ):
        mock_static.return_value = [
            _resort("kirkwood").model_dump(),
            _resort("alta").model_dump(),
        ]
        resp = client.get("/api/v1/resorts?sort_by=name")
        assert [r["resort_id"] for r in resp.json()["resorts"]] == ["alta", "kirkwood"]


class TestResortDetailAndNearby:
    @patch("handlers.api_handler.get_resort_service")
    def test_detail_includes_season_fields(self, mock_svc, client, with_entries):
        svc = MagicMock()
        svc.get_resort.return_value = _resort("kirkwood")
        mock_svc.return_value = svc
        resp = client.get("/api/v1/resorts/kirkwood")
        assert resp.status_code == 200
        body = resp.json()
        assert body["opening_date"] == "2099-12-04"
        assert body["season_status"] == "pre_season"

    @patch("handlers.api_handler.get_resort_service")
    def test_detail_not_found_still_404(self, mock_svc, client, with_entries):
        svc = MagicMock()
        svc.get_resort.return_value = None
        mock_svc.return_value = svc
        assert client.get("/api/v1/resorts/nope").status_code == 404

    @patch("handlers.api_handler.get_resort_service")
    def test_nearby_includes_season_fields(self, mock_svc, client, with_entries):
        svc = MagicMock()
        svc.get_nearby_resorts.return_value = [
            (_resort("kirkwood"), 12.5),
            (_resort("homewood"), 30.1),
        ]
        mock_svc.return_value = svc
        resp = client.get("/api/v1/resorts/nearby?lat=38.7&lon=-120.0")
        assert resp.status_code == 200
        results = resp.json()["resorts"]
        assert results[0]["resort"]["opening_date"] == "2099-12-04"
        assert results[0]["distance_km"] == 12.5
        assert results[1]["resort"]["opening_date"] is None
        assert results[1]["distance_km"] == 30.1


class TestStaticResortsJson:
    def test_resorts_json_includes_season_fields(self):
        from services.static_json_generator import StaticJsonGenerator

        with (
            patch("services.static_json_generator.dynamodb") as mock_db,
            patch("services.static_json_generator.s3_client") as mock_s3,
        ):
            table = MagicMock()
            table.scan.return_value = {
                "Items": [
                    {
                        "resort_id": rid,
                        "name": rid,
                        "country": "US",
                        "region": "CA",
                        "timezone": "America/Los_Angeles",
                        "elevation_points": [
                            {
                                "level": "base",
                                "elevation_meters": 2377,
                                "elevation_feet": 7800,
                                "latitude": 38.68,
                                "longitude": -120.07,
                            }
                        ],
                    }
                    for rid in ("kirkwood", "homewood")
                ]
            }
            mock_db.Table.return_value = table
            now = datetime.now(UTC).isoformat()
            body = MagicMock()
            body.read.return_value = json.dumps(
                {"resorts": {"kirkwood": {**ENTRIES["kirkwood"], "fetched_at": now}}}
            ).encode()
            mock_s3.get_object.return_value = {"Body": body}

            generator = StaticJsonGenerator(
                resorts_table_name="t",
                weather_conditions_table_name="w",
                website_bucket="test-bucket",
            )
            generator._generate_resorts_json()

            uploaded = json.loads(mock_s3.put_object.call_args.kwargs["Body"])
            by_id = {r["resort_id"]: r for r in uploaded["resorts"]}
            assert by_id["kirkwood"]["opening_date"] == "2099-12-04"
            assert by_id["kirkwood"]["season_status"] == "pre_season"
            assert by_id["homewood"]["opening_date"] is None
            mock_s3.get_object.assert_called_with(
                Bucket="test-bucket", Key="data/season-dates.json"
            )
