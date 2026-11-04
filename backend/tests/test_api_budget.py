"""Tests for the weather API refresh discipline (quota burn fix).

Covers the daily budget guard, the circuit breaker, demand-driven/TTL refresh
selection, one WeatherKit call per resort, 429 handling, and a 24-hour
call-volume simulation of the scheduled pipeline (before vs after).
"""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
import requests
from moto import mock_aws

from services.api_budget import (
    ApiBudget,
    get_demand_resort_ids,
    next_utc_midnight,
    record_demand,
)

TABLE = "snow-tracker-api-budget-test"


@pytest.fixture
def budget_table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-west-2")
        ddb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield ddb


def _budget(ddb, limit, block=5, provider="weatherkit"):
    return ApiBudget(
        provider, limit, table_name=TABLE, dynamodb_resource=ddb, block_size=block
    )


class TestApiBudget:
    def test_in_memory_limit(self):
        b = ApiBudget("openmeteo", 3, table_name="")
        assert [b.try_consume() for _ in range(5)] == [True, True, True, False, False]
        assert b.used == 3
        assert b.denied == 2

    def test_shared_counter_is_a_hard_cap_across_workers(self, budget_table):
        workers = [_budget(budget_table, limit=20, block=5) for _ in range(3)]
        allowed = 0
        for _ in range(20):
            for w in workers:
                allowed += w.try_consume()
        assert allowed <= 20
        # Blocks are reserved, so at least limit - workers * block get through
        assert allowed >= 20 - 3 * 5
        item = budget_table.Table(TABLE).scan()["Items"][0]
        assert int(item["calls"]) <= 20

    def test_exact_cost_used_near_the_limit(self, budget_table):
        b = _budget(budget_table, limit=7, block=5)
        results = [b.try_consume() for _ in range(9)]
        assert sum(results) == 7

    def test_trip_blocks_all_instances(self, budget_table):
        a = _budget(budget_table, limit=1000)
        b = _budget(budget_table, limit=1000)
        assert a.try_consume(2)
        a.trip(next_utc_midnight(), "OVER_QUOTA")
        assert not a.try_consume(2)
        # A fresh worker sees the breaker through the shared item
        assert not b.try_consume(2)
        assert b.is_tripped()

    def test_expired_trip_allows_calls_again(self, budget_table):
        a = _budget(budget_table, limit=1000)
        a.trip(datetime.now(UTC).timestamp() - 1, "old")
        assert a.try_consume()

    def test_next_utc_midnight(self):
        now = datetime(2026, 11, 3, 19, 18, tzinfo=UTC)
        assert next_utc_midnight(now) == datetime(2026, 11, 4, tzinfo=UTC).timestamp()


class TestDemand:
    def test_record_and_read_demand(self, budget_table):
        table = budget_table.Table(TABLE)
        record_demand("whistler", table=table)
        record_demand("zermatt", table=table)
        # Budget items are not demand
        table.put_item(Item={"pk": "budget#openmeteo#2026-11-04", "calls": 5})
        # Expired demand is ignored even before TTL deletion
        table.put_item(Item={"pk": "demand#old", "resort_id": "old", "expires_at": 1})
        assert get_demand_resort_ids(table=table) == {"whistler", "zermatt"}

    def test_no_table_configured_is_a_noop(self):
        with patch("services.api_budget.API_BUDGET_TABLE", ""):
            record_demand("whistler")
            assert get_demand_resort_ids() == set()


def _resorts(n):
    return [SimpleNamespace(resort_id=f"resort-{i}", region="alps") for i in range(n)]


class TestSelectDueResorts:
    def test_demand_resorts_every_hour_cold_once_per_cycle(self):
        from handlers.weather_processor import select_due_resorts

        resorts = _resorts(200)
        demand = {"resort-1", "resort-2"}
        seen: dict[str, int] = {}
        start = datetime(2026, 11, 4, tzinfo=UTC)
        for h in range(6):
            due, hot = select_due_resorts(
                resorts, demand, start + timedelta(hours=h), 6
            )
            assert hot == 2
            for r in due:
                seen[r.resort_id] = seen.get(r.resort_id, 0) + 1
        assert seen["resort-1"] == 6
        assert seen["resort-2"] == 6
        cold = [rid for rid in seen if rid not in demand]
        # Every cold resort refreshed exactly once in a 6h cycle
        assert len(cold) == 198
        assert all(seen[rid] == 1 for rid in cold)

    def test_cold_load_is_spread_over_the_hours(self):
        from handlers.weather_processor import select_due_resorts

        resorts = _resorts(1019)
        start = datetime(2026, 11, 4, tzinfo=UTC)
        sizes = [
            len(select_due_resorts(resorts, set(), start + timedelta(hours=h), 6)[0])
            for h in range(6)
        ]
        assert sum(sizes) == 1019
        assert max(sizes) < 1019 / 6 * 1.3

    def test_orchestrator_dispatches_only_due_resorts(self):
        from handlers.weather_processor import orchestrate_parallel_processing

        resorts = _resorts(60)
        module = "handlers.weather_processor"
        with (
            patch(f"{module}.dynamodb"),
            patch(f"{module}.ResortService") as rs,
            patch(f"{module}.lambda_client") as lc,
            patch(f"{module}.is_in_active_window", return_value=True),
            patch(f"{module}.get_demand_resort_ids", return_value={"resort-0"}),
            patch(f"{module}.get_favorite_resort_ids", return_value={"resort-1"}),
            patch(f"{module}.COLD_REFRESH_HOURS", 6),
        ):
            rs.return_value.get_all_resorts.return_value = resorts
            lc.invoke.return_value = {"StatusCode": 202}
            body = json.loads(orchestrate_parallel_processing(None)["body"])
            dispatched = {
                rid
                for call in lc.invoke.call_args_list
                for rid in json.loads(call.kwargs["Payload"])["resort_ids"]
            }
        assert {"resort-0", "resort-1"} <= dispatched
        assert body["demand_resorts"] == 2
        assert body["total_resorts"] == len(dispatched) < 60

    def test_force_all_dispatches_everything(self):
        from handlers.weather_processor import orchestrate_parallel_processing

        module = "handlers.weather_processor"
        with (
            patch(f"{module}.dynamodb"),
            patch(f"{module}.ResortService") as rs,
            patch(f"{module}.lambda_client") as lc,
            patch(f"{module}.is_in_active_window", return_value=True),
            patch(f"{module}.get_demand_resort_ids", return_value=set()),
            patch(f"{module}.get_favorite_resort_ids", return_value=set()),
        ):
            rs.return_value.get_all_resorts.return_value = _resorts(60)
            lc.invoke.return_value = {"StatusCode": 202}
            body = json.loads(
                orchestrate_parallel_processing(None, force_all=True)["body"]
            )
        assert body["total_resorts"] == 60


WORKER = "handlers.weather_worker"


def _resort_data(resort_id, points=3):
    levels = ["base", "mid", "top"][:points]
    return {
        "resort_id": resort_id,
        "name": resort_id,
        "elevation_points": [
            {"level": lvl, "latitude": 46.0, "longitude": 7.7, "elevation_meters": e}
            for lvl, e in zip(levels, [1600, 2200, 2900], strict=False)
        ],
    }


def _run_worker(resorts, weatherkit=None, pep=None, budgets=None, remaining=300000):
    from handlers.weather_worker import weather_worker_handler

    ctx = SimpleNamespace(get_remaining_time_in_millis=lambda: remaining)
    budgets = budgets or {}

    def make_budget(provider, limit):
        return budgets.get(provider) or ApiBudget(provider, limit, table_name="")

    with (
        patch(f"{WORKER}.dynamodb"),
        patch(f"{WORKER}.batch_get_all", return_value=resorts),
        patch(f"{WORKER}.OpenMeteoService"),
        patch(f"{WORKER}.SnowQualityService"),
        patch(f"{WORKER}.SnowSummaryService"),
        patch(f"{WORKER}.DailyHistoryService"),
        patch(f"{WORKER}.ENABLE_SCRAPING", False),
        patch(f"{WORKER}.INTER_RESORT_DELAY", 0.0),
        patch(f"{WORKER}.ENABLE_WEATHERKIT", weatherkit is not None),
        patch(f"{WORKER}.ApiBudget", side_effect=make_budget),
        patch("services.weatherkit_service.WeatherKitService", return_value=weatherkit),
        patch(f"{WORKER}.process_elevation_point", side_effect=pep) as mock_pep,
    ):
        result = weather_worker_handler(
            {"resort_ids": [r["resort_id"] for r in resorts], "region": "alps"}, ctx
        )
    return json.loads(result["body"])["stats"], mock_pep


def _ok(*args, **kwargs):
    return {"success": True, "error": None, "level": "mid"}


class TestWorkerCallPattern:
    def test_weatherkit_called_once_per_resort_and_shared_by_points(self):
        wk = MagicMock(configured=True)
        wk.get_weather.return_value = "wk-data"
        stats, pep = _run_worker(
            [_resort_data("a"), _resort_data("b")], weatherkit=wk, pep=_ok
        )
        assert wk.get_weather.call_count == 2  # not 6
        assert pep.call_count == 6
        # Every elevation point gets the resort's single WeatherKit result
        assert all(c.args[10] == "wk-data" for c in pep.call_args_list)
        assert stats["conditions_saved"] == 6

    def test_tripped_weatherkit_is_not_called(self):
        wk = MagicMock(configured=True)
        wk_budget = ApiBudget("weatherkit", 1000, table_name="")
        wk_budget.trip(next_utc_midnight(), "OVER_QUOTA")
        _run_worker(
            [_resort_data("a")],
            weatherkit=wk,
            pep=_ok,
            budgets={"weatherkit": wk_budget},
        )
        wk.get_weather.assert_not_called()

    def test_openmeteo_budget_exhausted_stops_batch(self):
        def pep(*args, **kwargs):
            budget = args[11]
            if not budget.try_consume(1):
                return {"success": False, "over_budget": True, "level": "mid"}
            return _ok()

        om_budget = ApiBudget("openmeteo", 4, table_name="")
        stats, mock_pep = _run_worker(
            [_resort_data(f"r{i}") for i in range(5)],
            pep=pep,
            budgets={"openmeteo": om_budget},
        )
        assert stats["conditions_saved"] == 4
        assert stats["stopped_early"] == "openmeteo_budget"
        assert mock_pep.call_count == 6  # 2 resorts, then stop

    def test_429_burst_trips_backoff_and_stops(self):
        def pep(*args, **kwargs):
            return {"success": False, "rate_limited": True, "level": "mid"}

        om_budget = ApiBudget("openmeteo", 1000, table_name="")
        stats, mock_pep = _run_worker(
            [_resort_data(f"r{i}") for i in range(10)],
            pep=pep,
            budgets={"openmeteo": om_budget},
        )
        assert om_budget.is_tripped()
        assert stats["stopped_early"] == "openmeteo_backoff"
        assert mock_pep.call_count == 6  # 5 x 429 reached after 2 resorts

    def test_stops_before_timeout(self):
        stats, pep = _run_worker([_resort_data("a")], pep=_ok, remaining=30000)
        assert stats["stopped_early"] == "time"
        pep.assert_not_called()

    def test_process_elevation_point_flags_429(self):
        from handlers.weather_worker import process_elevation_point

        resp = requests.Response()
        resp.status_code = 429
        ws = MagicMock()
        ws.get_current_weather.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
        result = process_elevation_point(
            _resort_data("a")["elevation_points"][0],
            "a",
            ws,
            MagicMock(),
            MagicMock(),
            None,
            None,
        )
        assert result["rate_limited"] is True

    def test_process_elevation_point_respects_budget(self):
        from handlers.weather_worker import process_elevation_point

        ws = MagicMock()
        result = process_elevation_point(
            _resort_data("a")["elevation_points"][0],
            "a",
            ws,
            MagicMock(),
            MagicMock(),
            None,
            None,
            openmeteo_budget=ApiBudget("openmeteo", 0, table_name=""),
        )
        assert result["over_budget"] is True
        ws.get_current_weather.assert_not_called()


class TestWeatherKitBudget:
    def _service(self):
        from services.weatherkit_service import WeatherKitService

        svc = WeatherKitService.__new__(WeatherKitService)
        svc.configured = True
        svc.session = MagicMock()
        svc._get_jwt_token = lambda: "token"
        return svc

    def test_over_quota_trips_until_next_utc_day(self):
        svc = self._service()
        resp = requests.Response()
        resp.status_code = 401
        resp._content = b'{"reason":"OVER_QUOTA"}'
        svc.session.get.return_value = resp
        budget = ApiBudget("weatherkit", 1000, table_name="")
        assert svc.get_weather(46.0, 7.7, "a", budget=budget) is None
        assert budget.is_tripped()
        assert svc.get_weather(46.0, 7.7, "a", budget=budget) is None
        assert svc.session.get.call_count == 1  # second call never sent

    def test_budget_counts_two_units_per_request(self):
        svc = self._service()
        svc.session.get.return_value = MagicMock(
            raise_for_status=lambda: None, json=lambda: {}
        )
        budget = ApiBudget("weatherkit", 4, table_name="")
        for _ in range(3):
            svc.get_weather(46.0, 7.7, "a", budget=budget)
        assert svc.session.get.call_count == 2


class TestOpenMeteo429:
    def test_429_is_not_retried(self):
        from services import openmeteo_service

        resp = requests.Response()
        resp.status_code = 429
        with (
            patch.object(openmeteo_service.requests, "request", return_value=resp),
            patch.object(openmeteo_service.time, "sleep") as sleep,
        ):
            with pytest.raises(requests.exceptions.HTTPError):
                openmeteo_service._request_with_retry("GET", "https://x", timeout=1)
            sleep.assert_not_called()


class TestDailyCallVolume:
    """24h simulation of the scheduled pipeline, 1,019 resorts x 3 points."""

    RESORTS = 1019
    DEMAND = 50

    def _simulate(self, cold_hours, demand):
        from handlers.weather_processor import select_due_resorts

        resorts = _resorts(self.RESORTS)
        start = datetime(2026, 11, 4, tzinfo=UTC)
        resort_refreshes = 0
        for h in range(24):
            due, _ = select_due_resorts(
                resorts, demand, start + timedelta(hours=h), cold_hours
            )
            resort_refreshes += len(due)
        return {
            "openmeteo_forecast": resort_refreshes * 3,  # one per elevation point
            "weatherkit": resort_refreshes,  # one per resort (was one per point)
        }

    def test_before_and_after(self):
        demand = {f"resort-{i}" for i in range(self.DEMAND)}
        # Before: every resort every hour, WeatherKit once per point
        before_openmeteo = self.RESORTS * 3 * 24
        before_weatherkit = self.RESORTS * 3 * 24
        assert before_weatherkit == 73_368

        after = self._simulate(6, demand)
        expected_refreshes = self.DEMAND * 24 + (self.RESORTS - self.DEMAND) * 4
        assert after["weatherkit"] == expected_refreshes == 5_076  # per day
        assert after["openmeteo_forecast"] == 15_228  # per day
        # Fits Apple's 500k/month even if each request counts per data set (x2)
        assert after["weatherkit"] * 2 * 31 < 500_000
        assert after["openmeteo_forecast"] < before_openmeteo / 4
