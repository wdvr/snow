"""Tests for the "Best this weekend" ranking (services/weekend_ranking_service.py).

The fixture tests replay the Tahoe storm week of Nov 16-20, 2026 as recorded on
Friday evening Nov 20 (see tests/fixtures/weekend_storm_2026_11_20.json _meta).
"""

import json
import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from models.resort import ElevationLevel, ElevationPoint, Resort
from services import weekend_ranking_service as wr
from services.onthesnow_scraper import OnTheSnowScraper, terrain_fields
from utils.cache import clear_all_caches

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "weekend_storm_2026_11_20.json"
)

FRI = date(2026, 11, 20)
SAT = date(2026, 11, 21)
SUN = date(2026, 11, 22)


def _fixture() -> dict:
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def _fixture_inputs() -> tuple[list[wr.ResortWeekendInput], date]:
    """Build ranking inputs from the fixture through the production assembly."""
    data = _fixture()
    today = date.fromisoformat(data["_meta"]["today"])
    restrictions = {
        rid: [
            wr.AccessRestriction(
                start=date.fromisoformat(e["start"]),
                end=date.fromisoformat(e["end"]),
                kind=e["kind"],
                eligible_passes=e["eligible_passes"],
                note=e["note"],
            )
            for e in entries
        ]
        for rid, entries in data["restrictions"].items()
    }
    overrides = {k: date.fromisoformat(v) for k, v in data["opening_dates"].items()}
    inputs = []
    for r in data["resorts"]:
        resort = SimpleNamespace(
            **{k: v for k, v in r.items() if k not in ("conditions", "history")}
        )
        conditions = [SimpleNamespace(**c) for c in r["conditions"]]
        forecast = {date.fromisoformat(d): v for d, v in r["forecast_daily_cm"].items()}
        inputs.append(
            wr.build_input(
                resort,
                conditions,
                r["history"],
                forecast,
                restrictions.get(r["resort_id"], []),
                today,
                opening_override=overrides.get(r["resort_id"]),
            )
        )
    return inputs, today


def _by_id(rankings):
    return {r.resort_id: r for r in rankings}


def _accessible(rankings):
    return [r for r in rankings if r.accessible_days > 0]


# MARK: - Window


class TestWeekendWindow:
    @pytest.mark.parametrize(
        "today,expected",
        [
            (date(2026, 11, 16), (FRI, SUN)),  # Monday -> coming weekend
            (date(2026, 11, 19), (FRI, SUN)),  # Thursday
            (FRI, (FRI, SUN)),  # Friday -> starts today
            (SAT, (SAT, SUN)),  # Saturday -> clipped to today
            (SUN, (SUN, SUN)),  # Sunday -> just today
        ],
    )
    def test_default_window(self, today, expected):
        assert wr.weekend_window(today) == expected

    def test_resolve_defaults_to_weekend(self):
        assert wr.resolve_window(date(2026, 11, 18)) == (FRI, SUN)

    def test_custom_range(self):
        assert wr.resolve_window(FRI, SAT, date(2026, 11, 24)) == (
            SAT,
            date(2026, 11, 24),
        )

    @pytest.mark.parametrize(
        "start,end,message",
        [
            (SAT, None, "Both start and end"),
            (SUN, SAT, "on or after"),
            (date(2026, 11, 19), SAT, "past"),
            (SAT, date(2026, 12, 5), "exceed"),
            (date(2026, 12, 4), date(2026, 12, 6), "within"),
        ],
    )
    def test_invalid_ranges(self, start, end, message):
        with pytest.raises(ValueError, match=message):
            wr.resolve_window(FRI, start, end)


# MARK: - Access


def _resort(**kwargs) -> wr.ResortWeekendInput:
    defaults = {
        "resort_id": "test",
        "name": "Test",
        "opening_date": date(2026, 11, 1),
        "season_status": "open",
    }
    defaults.update(kwargs)
    return wr.ResortWeekendInput(**defaults)


PASSHOLDER = wr.AccessRestriction(
    start=SAT,
    end=date(2026, 11, 26),
    eligible_passes=["sugar-bowl"],
    note="Season passholders only",
)


class TestDayAccess:
    def test_open(self):
        assert wr.day_access(_resort(), SAT, set()) == ("open", None)

    def test_before_opening(self):
        access, note = wr.day_access(_resort(opening_date=SAT), FRI, set())
        assert access == "closed"
        assert note == "Opens Nov 21"

    def test_after_closing(self):
        r = _resort(closing_date=FRI)
        assert wr.day_access(r, SAT, set())[0] == "closed"

    def test_post_season(self):
        assert wr.day_access(_resort(season_status="post_season"), SAT, set())[0] == (
            "closed"
        )

    def test_passholder_only(self):
        r = _resort(restrictions=[PASSHOLDER])
        assert wr.day_access(r, SAT, set()) == (
            "passholder_only",
            "Season passholders only",
        )
        assert wr.day_access(r, date(2026, 11, 27), set())[0] == "open"

    def test_eligible_pass_unlocks_passholder_day(self):
        r = _resort(restrictions=[PASSHOLDER])
        access, note = wr.day_access(r, SAT, {"sugar-bowl"})
        assert access == "open"
        assert "your pass" in note

    def test_other_pass_does_not_unlock(self):
        r = _resort(restrictions=[PASSHOLDER])
        assert wr.day_access(r, SAT, {"ikon", "epic"})[0] == "passholder_only"

    def test_closed_restriction(self):
        r = _resort(
            restrictions=[
                wr.AccessRestriction(start=SAT, end=SAT, kind="closed", note="Wind")
            ]
        )
        assert wr.day_access(r, SAT, set()) == ("closed", "Wind")

    def test_unknown_without_season_data(self):
        r = _resort(opening_date=None, season_status=None)
        assert wr.day_access(r, SAT, set())[0] == "unknown"

    def test_passes_normalized(self):
        assert wr.normalize_passes([" Ikon", "EPIC", ""]) == {"ikon", "epic"}


# MARK: - Scoring


class TestScoring:
    def test_terrain_prefers_runs_then_lifts(self):
        assert wr.terrain_share(_resort(runs_open=25, runs_total=100)) == 0.25
        assert wr.terrain_share(_resort(lifts_open=3, lifts_total=6)) == 0.5
        assert wr.terrain_share(_resort()) is None
        assert wr.terrain_share(_resort(runs_open=12, runs_total=10)) == 1.0

    def test_powder_counts_previous_day_and_half_of_today(self):
        forecast = {FRI: 20.0, SAT: 10.0}
        assert wr.powder_cm(forecast, SAT) == 25.0
        assert wr.powder_cm(forecast, SUN) == 10.0

    def test_more_snow_scores_higher(self):
        low = _resort(forecast_daily_cm={SAT: 2.0, SUN: 0.0}, base_depth_cm=50)
        high = _resort(forecast_daily_cm={SAT: 30.0, SUN: 10.0}, base_depth_cm=50)
        assert (
            wr.score_resort(high, SAT, SUN).score > wr.score_resort(low, SAT, SUN).score
        )

    def test_missing_components_renormalized_and_flagged(self):
        r = _resort(forecast_daily_cm={SAT: 25.0, SUN: 0.0})
        ranking = wr.score_resort(r, SAT, SUN)
        # Only the forecast signal: 1 - e^-1 = 0.632
        assert ranking.score == 63
        assert set(ranking.components) == {"forecast"}
        assert "No base depth data" in ranking.flags
        assert "No lift/terrain data" in ranking.flags
        assert "No recent snowfall data" in ranking.flags

    def test_no_data_gives_no_score(self):
        ranking = wr.score_resort(_resort(), SAT, SUN)
        assert ranking.score is None
        assert ranking.reason == "Not enough data to rank"

    def test_partial_access_scales_score(self):
        base = {
            "forecast_daily_cm": {SAT: 10.0, SUN: 10.0},
            "base_depth_cm": 100,
            "snowfall_7d_cm": 40,
            "runs_open": 50,
            "runs_total": 100,
        }
        full = wr.score_resort(_resort(**base), SAT, SUN)
        half = wr.score_resort(_resort(opening_date=SUN, **base), SAT, SUN)
        assert half.access_status == "partial"
        assert half.accessible_days == 1
        assert (
            half.score == round(full.score * 0.75)
            or abs(half.score - full.score * 0.75) <= 1
        )

    def test_best_day_labels(self):
        r = _resort(forecast_daily_cm={FRI: 30.0, SAT: 0.0, SUN: 2.0})
        ranking = wr.score_resort(r, SAT, SUN)
        assert ranking.best_day == "2026-11-21"
        assert ranking.best_day_label == "powder day"
        dry = wr.score_resort(_resort(forecast_daily_cm={SAT: 0.0}), SAT, SUN)
        assert dry.best_day == "2026-11-21"
        assert dry.best_day_label == "groomers"

    def test_best_day_skips_inaccessible_days(self):
        r = _resort(
            forecast_daily_cm={FRI: 30.0, SAT: 0.0, SUN: 0.0}, restrictions=[PASSHOLDER]
        )
        ranking = wr.score_resort(r, SAT, SUN)
        assert ranking.best_day is None
        assert ranking.access_status == "passholder_only"

    def test_reason_shows_deciding_numbers(self):
        r = _resort(
            forecast_daily_cm={SAT: 10.0, SUN: 5.0},
            snowfall_7d_cm=60,
            base_depth_cm=120,
            runs_open=45,
            runs_total=100,
        )
        reason = wr.score_resort(r, SAT, SUN).reason
        assert reason == (
            "15 cm forecast Sat-Sun · 60 cm last 7 days · 120 cm base · "
            "45% terrain open"
        )

    def test_rank_puts_inaccessible_last_and_breaks_ties(self):
        snow = {SAT: 20.0, SUN: 20.0}
        rankings = wr.rank_resorts(
            [
                _resort(resort_id="b", name="B", forecast_daily_cm={SAT: 1.0}),
                _resort(
                    resort_id="locked",
                    name="Locked",
                    forecast_daily_cm=snow,
                    restrictions=[PASSHOLDER],
                ),
                _resort(resort_id="a", name="A", forecast_daily_cm={SAT: 1.0}),
                _resort(resort_id="nodata", name="No data"),
            ],
            SAT,
            SUN,
        )
        assert [r.resort_id for r in rankings] == ["a", "b", "nodata", "locked"]
        assert [r.rank for r in rankings] == [1, 2, 3, 4]

    def test_to_dict_shape(self):
        r = _resort(forecast_daily_cm={SAT: 10.04}, base_depth_cm=99.96)
        d = wr.score_resort(r, SAT, SUN).to_dict()
        assert d["forecast_window_cm"] == 10.0
        assert d["base_depth_cm"] == 100.0
        assert d["days"][0] == {
            "date": "2026-11-21",
            "access": "open",
            "forecast_snow_cm": 10.0,
            "powder_cm": 5.0,
            "note": None,
        }
        for key in (
            "rank",
            "score",
            "snowfall_7d_cm",
            "terrain_open_pct",
            "access_status",
            "flags",
            "reason",
            "best_day_label",
        ):
            assert key in d


# MARK: - Input assembly


class TestBuildInput:
    def _resort_ns(self, **kwargs):
        defaults = {
            "resort_id": "r",
            "name": "R",
            "region": "na_west",
            "state_province": "CA",
            "ikon_pass": "full",
            "epic_pass": None,
            "mountain_collective": "2 days",
            "indy_pass": None,
            "opening_date": "2026-11-21",
            "closing_date": None,
            "season_status": "pre_season",
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_assembles_from_pipeline_data(self):
        conditions = [
            SimpleNamespace(
                elevation_level="mid", snow_depth_cm=90.0, lifts_open=3, lifts_total=6
            ),
            SimpleNamespace(elevation_level="base", snow_depth_cm=60.0),
        ]
        history = [
            {"date": "2026-11-13", "snowfall_24h_cm": 50.0},  # outside 7 days
            {"date": "2026-11-18", "snowfall_24h_cm": 10.0},
            {"date": "2026-11-20", "snowfall_24h_cm": 5.5},
        ]
        result = wr.build_input(self._resort_ns(), conditions, history, {}, [], FRI)
        assert result.base_depth_cm == 60.0  # base level preferred
        assert result.snowfall_7d_cm == 15.5
        assert result.lifts_open == 3
        assert result.passes == ["ikon", "mountain_collective"]
        assert result.opening_date == SAT
        assert result.season_status == "pre_season"

    def test_falls_back_to_72h_without_history(self):
        conditions = [SimpleNamespace(elevation_level="mid", snowfall_72h_cm=33.0)]
        result = wr.build_input(self._resort_ns(), conditions, [], {}, [], FRI)
        assert result.snowfall_7d_cm == 33.0

    def test_opening_override_wins_and_fixes_stale_status(self):
        r = self._resort_ns(opening_date="2026-12-04", season_status="pre_season")
        result = wr.build_input(r, [], [], {}, [], SAT, opening_override=SAT)
        assert result.opening_date == SAT
        assert result.season_status == "open"

    def test_future_override_keeps_status(self):
        r = self._resort_ns(opening_date="2026-12-04", season_status="pre_season")
        override = date(2026, 11, 23)
        result = wr.build_input(r, [], [], {}, [], SAT, opening_override=override)
        assert result.opening_date == override
        assert result.season_status == "pre_season"


class TestAccessRestrictionsFile:
    def test_shipped_file_loads_with_sources(self):
        restrictions = wr.load_access_restrictions()
        sugar = restrictions["sugar-bowl"]
        assert sugar[0].kind == "passholder_only"
        assert sugar[0].eligible_passes == ["sugar-bowl"]
        assert sugar[0].covers(date(2026, 11, 22))
        assert not sugar[0].covers(date(2026, 11, 27))
        with open(wr._RESTRICTIONS_PATH) as f:
            raw = json.load(f)
        for entries in raw["restrictions"].values():
            for entry in entries:
                assert entry["source"].startswith("https://")
        for entry in raw["opening_dates"].values():
            assert entry["source"].startswith("https://")

    def test_shipped_opening_overrides(self):
        overrides = wr.load_opening_overrides()
        assert overrides["palisades-tahoe"] == SAT
        assert overrides["mt-rose"] == date(2026, 11, 6)

    def test_missing_file_is_empty(self, tmp_path):
        missing = str(tmp_path / "nope.json")
        assert wr.load_access_restrictions(missing) == {}
        assert wr.load_opening_overrides(missing) == {}

    def test_skips_entries_without_dates(self, tmp_path):
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"restrictions": {"x": [{"start": "2026-11-21"}]}}))
        assert wr.load_access_restrictions(str(path)) == {"x": []}


# MARK: - Storm week fixture (Nov 16-20, 2026)


class TestStormWeekFixture:
    """Friday Nov 20 evening: "where is predicted best this weekend?"."""

    @pytest.fixture()
    def rankings(self):
        inputs, today = _fixture_inputs()
        start, end = wr.weekend_window(today)
        assert (start, end) == (FRI, SUN)
        return wr.rank_resorts(inputs, start, end)

    def test_mt_rose_has_deepest_base_of_open_resorts(self, rankings):
        accessible = _accessible(rankings)
        deepest = max(accessible, key=lambda r: r.base_depth_cm or 0)
        assert deepest.resort_id == "mt-rose"
        assert deepest.base_depth_cm == pytest.approx(71.1)

    def test_palisades_has_most_forecast_snow_of_open_resorts(self, rankings):
        accessible = _accessible(rankings)
        most = max(accessible, key=lambda r: r.forecast_window_cm or 0)
        assert most.resort_id == "palisades-tahoe"
        assert most.forecast_window_cm == pytest.approx(13.4)

    def test_palisades_sunday_is_its_best_day(self, rankings):
        palisades = _by_id(rankings)["palisades-tahoe"]
        assert palisades.best_day == "2026-11-22"
        # Closed Friday (opens Sat Nov 21), open Sat + Sun
        assert palisades.access_status == "partial"
        assert [d.access for d in palisades.days] == ["closed", "open", "open"]
        assert "Opens Nov 21" in palisades.flags

    def test_sugar_bowl_flagged_passholder_only(self, rankings):
        sugar = _by_id(rankings)["sugar-bowl"]
        assert sugar.access_status == "passholder_only"
        assert sugar.accessible_days == 0
        assert any(f.startswith("Passholders only 2 of 3 days") for f in sugar.flags)
        assert [d.access for d in sugar.days] == [
            "closed",
            "passholder_only",
            "passholder_only",
        ]

    def test_sugar_bowl_ranked_after_every_open_resort(self, rankings):
        sugar = _by_id(rankings)["sugar-bowl"]
        assert all(r.rank < sugar.rank for r in _accessible(rankings))
        # ...even though it has more base and forecast snow than any of them
        assert all(sugar.base_depth_cm > r.base_depth_cm for r in _accessible(rankings))
        assert all(
            sugar.forecast_window_cm > r.forecast_window_cm
            for r in _accessible(rankings)
        )

    def test_sugar_bowl_pass_unlocks_it(self):
        inputs, today = _fixture_inputs()
        rankings = wr.rank_resorts(inputs, FRI, SUN, ["sugar-bowl"])
        sugar = _by_id(rankings)["sugar-bowl"]
        assert sugar.access_status == "partial"
        assert sugar.accessible_days == 2
        assert not any("Passholders only" in f for f in sugar.flags)
        # Joins the skiable group, ahead of the thin-base Epic resorts
        northstar = _by_id(rankings)["northstar"]
        assert sugar.rank < northstar.rank

    def test_unopened_resorts_closed_and_last(self, rankings):
        by_id = _by_id(rankings)
        for rid in ("kirkwood", "sierra-at-tahoe", "homewood-mountain-resort"):
            assert by_id[rid].access_status == "closed"
        assert "Opens Nov 23" in by_id["kirkwood"].flags
        assert "Opens Dec 6" in by_id["sierra-at-tahoe"].flags
        assert {r.resort_id for r in rankings[-3:]} == {
            "kirkwood",
            "sierra-at-tahoe",
            "homewood-mountain-resort",
        }
        # Passholder-only sits between the skiable and the closed resorts
        assert by_id["sugar-bowl"].rank == len(rankings) - 3

    def test_zero_terrain_ignored_before_opening(self, rankings):
        sugar = _by_id(rankings)["sugar-bowl"]
        assert sugar.terrain_open_pct is None
        assert "terrain" not in sugar.components

    def test_top_three_are_the_open_resorts(self, rankings):
        top = [r.resort_id for r in rankings[:4]]
        assert set(top) == {"mt-rose", "palisades-tahoe", "northstar", "heavenly"}
        assert top[0] == "mt-rose"
        # Every row carries the deciding numbers
        for r in rankings[:4]:
            assert r.forecast_window_cm is not None
            assert r.snowfall_7d_cm is not None
            assert r.base_depth_cm is not None

    def test_extended_window_finds_midweek_storm(self):
        inputs, _ = _fixture_inputs()
        rankings = wr.rank_resorts(inputs, SAT, date(2026, 11, 26))
        accessible = _accessible(rankings)
        most = max(accessible, key=lambda r: r.forecast_window_cm or 0)
        assert most.resort_id == "palisades-tahoe"
        # Kirkwood opens Mon Nov 23 so it is skiable in the extended window
        kirkwood = _by_id(rankings)["kirkwood"]
        assert kirkwood.access_status == "partial"
        assert kirkwood.accessible_days == 4


# MARK: - Forecast fetch


def _resort_model(resort_id: str, lat: float = 39.2) -> Resort:
    return Resort(
        resort_id=resort_id,
        name=resort_id.title(),
        country="US",
        region="na_west",
        timezone="America/Los_Angeles",
        elevation_points=[
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=2300,
                elevation_feet=7546,
                latitude=lat,
                longitude=-120.2,
            )
        ],
    )


class TestFetchForecast:
    @patch("services.openmeteo_service._request_with_retry")
    def test_multi_location_response(self, mock_request):
        mock_request.return_value.json.return_value = [
            {
                "daily": {
                    "time": ["2026-11-21", "2026-11-22"],
                    "snowfall_sum": [0, 10.3],
                }
            },
            {"daily": {"time": ["2026-11-21"], "snowfall_sum": [None]}},
        ]
        result = wr.fetch_daily_snowfall_forecast(
            [_resort_model("a"), _resort_model("b", 39.3)]
        )
        assert result == {"a": {SAT: 0.0, SUN: 10.3}}
        params = mock_request.call_args.kwargs["params"]
        assert params["latitude"] == "39.2000,39.3000"
        assert params["elevation"] == "2300,2300"
        assert params["daily"] == "snowfall_sum"

    @patch("services.openmeteo_service._request_with_retry")
    def test_single_location_dict_response(self, mock_request):
        mock_request.return_value.json.return_value = {
            "daily": {"time": ["2026-11-21"], "snowfall_sum": [4.0]}
        }
        assert wr.fetch_daily_snowfall_forecast([_resort_model("a")]) == {
            "a": {SAT: 4.0}
        }

    @patch("services.openmeteo_service._request_with_retry")
    def test_failure_returns_empty(self, mock_request):
        mock_request.side_effect = Exception("boom")
        assert wr.fetch_daily_snowfall_forecast([_resort_model("a")]) == {}

    @patch("services.openmeteo_service._request_with_retry")
    def test_chunks_of_fifty(self, mock_request):
        mock_request.return_value.json.return_value = []
        wr.fetch_daily_snowfall_forecast([_resort_model(f"r{i}") for i in range(120)])
        assert mock_request.call_count == 3


# MARK: - Scraper terrain fields


class TestTerrainScrape:
    def test_label_first_layout(self):
        from bs4 import BeautifulSoup

        html = (
            "<html><body><div>Lifts & terrain</div><div>Lifts Open</div>"
            "<div>7 / 20</div><div>Runs Open</div><div>17 / 100</div>"
            "</body></html>"
        )
        scraper = OnTheSnowScraper()
        data = scraper._parse_from_regex(
            BeautifulSoup(html, "html.parser"), "northstar", "https://x"
        )
        assert (data.lifts_open, data.lifts_total) == (7, 20)
        assert (data.runs_open, data.runs_total) == (17, 100)

    def test_lifts_only_label_first_not_read_as_runs(self):
        from bs4 import BeautifulSoup

        html = "<p>Lifts Open 7 / 20 Runs</p>"
        data = OnTheSnowScraper()._parse_from_regex(
            BeautifulSoup(html, "html.parser"), "x", "https://x"
        )
        assert (data.lifts_open, data.lifts_total) == (7, 20)
        assert data.runs_open is None

    def test_count_first_layout_still_parsed(self):
        from bs4 import BeautifulSoup

        html = "<p>5 of 27 lifts open, 4 of 111 trails</p>"
        data = OnTheSnowScraper()._parse_from_regex(
            BeautifulSoup(html, "html.parser"), "x", "https://x"
        )
        assert (data.lifts_open, data.lifts_total) == (5, 27)
        assert (data.runs_open, data.runs_total) == (4, 111)

    def test_terrain_fields_filters_bad_values(self):
        data = SimpleNamespace(
            lifts_open=9, lifts_total=8, runs_open=4, runs_total=None
        )
        assert terrain_fields(data) == {"runs_open": 4}
        data = SimpleNamespace(lifts_open=3, lifts_total=8, runs_open=-1, runs_total=5)
        assert terrain_fields(data) == {
            "lifts_open": 3,
            "lifts_total": 8,
            "runs_total": 5,
        }


# MARK: - API endpoint


@pytest.fixture()
def client():
    from handlers.api_handler import app, reset_services

    clear_all_caches()
    reset_services()
    yield TestClient(app)
    clear_all_caches()


def _condition(level: str, depth: float):
    return SimpleNamespace(
        elevation_level=level,
        snow_depth_cm=depth,
        snowfall_72h_cm=20.0,
        lifts_open=4,
        lifts_total=8,
        runs_open=None,
        runs_total=None,
    )


class TestWeekendEndpoint:
    def _patches(self, resorts, forecasts, today=FRI):
        weather = MagicMock()
        weather.get_latest_conditions_all_elevations.side_effect = lambda rid: [
            _condition("base", 50.0 if rid == "a" else 80.0)
        ]
        history = MagicMock()
        history.get_history.return_value = [
            {"date": "2026-11-20", "snowfall_24h_cm": 10.0}
        ]
        return [
            patch("handlers.api_handler._get_all_resorts_cached", return_value=resorts),
            patch(
                "handlers.api_handler.fetch_daily_snowfall_forecast",
                return_value=forecasts,
            ),
            patch("handlers.api_handler.get_weather_service", return_value=weather),
            patch(
                "handlers.api_handler.get_daily_history_service", return_value=history
            ),
            patch(
                "handlers.api_handler._get_static_snow_quality_from_s3", return_value={}
            ),
            patch("handlers.api_handler.resort_today", return_value=today),
        ]

    def _get(self, client, url, resorts, forecasts, today=FRI):
        patches = self._patches(resorts, forecasts, today)
        for p in patches:
            p.start()
        try:
            return client.get(url)
        finally:
            for p in patches:
                p.stop()

    def test_ranks_favorites(self, client):
        resorts = [_resort_model("a"), _resort_model("b")]
        forecasts = {"a": {SAT: 2.0}, "b": {SAT: 20.0, SUN: 5.0}}
        resp = self._get(
            client,
            "/api/v1/rankings/weekend?resort_ids=a,b,unknown",
            resorts,
            forecasts,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["window"] == {
            "start": "2026-11-20",
            "end": "2026-11-22",
            "is_default_weekend": True,
        }
        assert body["scope"] == "favorites"
        assert [r["resort_id"] for r in body["rankings"]] == ["b", "a"]
        top = body["rankings"][0]
        assert top["rank"] == 1
        assert top["forecast_window_cm"] == 25.0
        assert top["base_depth_cm"] == 80.0
        assert top["snowfall_7d_cm"] == 10.0
        assert top["terrain_open_pct"] == 50.0

    def test_custom_window_and_passes(self, client):
        resorts = [_resort_model("a")]
        resp = self._get(
            client,
            "/api/v1/rankings/weekend?resort_ids=a&start=2026-11-21&end=2026-11-24"
            "&passes=ikon,epic",
            resorts,
            {"a": {SAT: 1.0}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["window"]["start"] == "2026-11-21"
        assert body["window"]["is_default_weekend"] is False
        assert body["passes"] == ["ikon", "epic"]
        assert body["rankings"][0]["window_days"] == 4

    def test_region_scope_filters(self, client):
        alps = _resort_model("alps-resort")
        alps.region = "alps"
        resp = self._get(
            client,
            "/api/v1/rankings/weekend?region=na_west",
            [_resort_model("a"), alps],
            {},
        )
        assert resp.status_code == 200
        assert [r["resort_id"] for r in resp.json()["rankings"]] == ["a"]
        assert resp.json()["scope"] == "region"

    def test_global_scope_skips_closed_for_window(self, client):
        closed = _resort_model("late")
        closed.opening_date = "2026-12-20"
        resp = self._get(
            client, "/api/v1/rankings/weekend", [_resort_model("a"), closed], {}
        )
        assert resp.status_code == 200
        assert resp.json()["scope"] == "global"
        assert [r["resort_id"] for r in resp.json()["rankings"]] == ["a"]

    @pytest.mark.parametrize(
        "query",
        [
            "start=2026-11-22",
            "start=2026-11-22&end=2026-11-21",
            "start=bad&end=2026-11-21",
            "region=mars",
            "resort_ids=bad$id",
            "passes=ik%20on",
        ],
    )
    def test_bad_requests(self, client, query):
        resp = self._get(
            client, f"/api/v1/rankings/weekend?{query}", [_resort_model("a")], {}
        )
        assert resp.status_code == 400

    def test_too_many_resorts(self, client):
        ids = ",".join(f"r{i}" for i in range(51))
        resp = self._get(client, f"/api/v1/rankings/weekend?resort_ids={ids}", [], {})
        assert resp.status_code == 400

    def test_cached_second_call(self, client):
        resorts = [_resort_model("a")]
        first = self._get(client, "/api/v1/rankings/weekend?resort_ids=a", resorts, {})
        second = self._get(client, "/api/v1/rankings/weekend?resort_ids=a", resorts, {})
        assert first.headers["X-Cache"] == "MISS"
        assert second.headers["X-Cache"] == "HIT"

    def test_cache_not_shared_across_days(self, client):
        """'Today' drives the 7-day history window and opening overrides, so a
        ranking cached on Friday must not be served on Saturday for the same
        explicit window."""
        resorts = [_resort_model("a")]
        url = "/api/v1/rankings/weekend?resort_ids=a&start=2026-11-21&end=2026-11-22"
        friday = self._get(client, url, resorts, {}, today=FRI)
        saturday = self._get(client, url, resorts, {}, today=SAT)
        assert friday.headers["X-Cache"] == "MISS"
        assert saturday.headers["X-Cache"] == "MISS"


class TestRankTiers:
    def test_passholder_only_before_closed(self):
        snow = {SAT: 30.0, SUN: 30.0}
        rankings = wr.rank_resorts(
            [
                _resort(
                    resort_id="closed",
                    name="Closed",
                    opening_date=date(2026, 12, 1),
                    forecast_daily_cm=snow,
                    base_depth_cm=200,
                ),
                _resort(
                    resort_id="locked",
                    name="Locked",
                    restrictions=[PASSHOLDER],
                    forecast_daily_cm={SAT: 1.0},
                ),
            ],
            SAT,
            SUN,
        )
        assert [r.resort_id for r in rankings] == ["locked", "closed"]

    def test_zero_terrain_counts_once_open(self):
        r = _resort(lifts_open=0, lifts_total=10, forecast_daily_cm={SAT: 1.0})
        ranking = wr.score_resort(r, SAT, SUN)
        assert ranking.terrain_open_pct == 0.0
        assert ranking.components["terrain"] == 0.0
