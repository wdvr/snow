"""Tests for season opening/closing dates (services/season_dates.py)."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from models.resort import ElevationLevel, ElevationPoint, Resort
from services import season_dates
from services.season_dates import (
    SEASON_DATES_S3_KEY,
    SEASON_FIELDS,
    STATUS_CLOSING_SOON,
    STATUS_OPEN,
    STATUS_POST_SEASON,
    STATUS_PRE_SEASON,
    STATUS_TEMPORARILY_CLOSED,
    apply_season_dates,
    derive_season_status,
    fresh_entries,
    load_season_dates,
    normalize_record,
    parse_onthesnow_records,
    resort_today,
    season_fields_for,
)

BACKEND = Path(__file__).resolve().parent.parent


def flight_html(*rows: str) -> str:
    """Wrap RSC flight rows the way Next.js embeds them in a page."""
    payload = "".join(r + "\n" for r in rows)
    half = len(payload) // 2
    chunks = [payload[:half], payload[half:]]
    return "".join(
        f"<script>self.__next_f.push([1,{json.dumps(c)}])</script>" for c in chunks
    )


KIRKWOOD_PAGE = flight_html(
    '1c:{"uuid":"201","title":"Kirkwood","slug":"kirkwood","region":"$1d",'
    '"status":"$2a","updatedAt":"2026-10-19T16:39:43+00:00"}',
    '1d:{"uuid":"311","slug":"california"}',
    '2a:{"openFlag":2,"openingDate":"2026-12-04","closingDate":"2027-04-11"}',
    '3c:{"uuid":"362","title":"Sierra-at-Tahoe","slug":"sierra-at-tahoe",'
    '"status":{"openFlag":2,"openingDate":"2026-12-06","closingDate":"2027-03-21"}}',
    '4c:{"date":"2026-11-16","snow":13.72}',
)


@pytest.fixture(autouse=True)
def _reset_cache():
    season_dates.clear_cache()
    yield
    season_dates.clear_cache()


def _resort(resort_id="kirkwood", tz="America/Los_Angeles") -> Resort:
    return Resort(
        resort_id=resort_id,
        name=resort_id.title(),
        country="US",
        region="CA",
        timezone=tz,
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


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class TestParseOnTheSnowRecords:
    def test_extracts_resort_and_neighbours(self):
        records = parse_onthesnow_records(KIRKWOOD_PAGE)
        assert set(records) == {"201", "362"}
        assert records["201"]["opening_date"] == "2026-12-04"
        assert records["201"]["closing_date"] == "2027-04-11"
        assert records["201"]["open_flag"] == 2
        assert records["201"]["slug"] == "kirkwood"
        # Inline (non-referenced) status objects work too
        assert records["362"]["opening_date"] == "2026-12-06"

    def test_page_without_payload_returns_empty(self):
        assert parse_onthesnow_records("<html><body>nothing</body></html>") == {}

    def test_ignores_malformed_rows(self):
        html = flight_html(
            "1a:{not json",
            '1b:{"uuid":"9","title":"X","slug":"x","status":"$zz"}',
        )
        # Unresolvable status reference -> no record
        assert parse_onthesnow_records(html) == {}


class TestNormalizeRecord:
    TODAY = date(2026, 11, 17)

    def test_valid_pair(self):
        out = normalize_record(
            {
                "open_flag": 2,
                "opening_date": "2026-12-04",
                "closing_date": "2027-04-11",
            },
            self.TODAY,
        )
        assert out == {
            "opening_date": "2026-12-04",
            "closing_date": "2027-04-11",
            "open_flag": 2,
        }

    def test_accepts_datetime_strings(self):
        out = normalize_record(
            {
                "open_flag": 2,
                "opening_date": "2026-12-04T00:00:00+00:00",
                "closing_date": None,
            },
            self.TODAY,
        )
        assert out["opening_date"] == "2026-12-04"
        assert out["closing_date"] is None

    def test_no_report_flag_dropped(self):
        assert (
            normalize_record(
                {
                    "open_flag": 6,
                    "opening_date": "2026-12-10",
                    "closing_date": "2027-03-05",
                },
                self.TODAY,
            )
            is None
        )

    def test_implausible_years_dropped(self):
        assert (
            normalize_record(
                {
                    "open_flag": 2,
                    "opening_date": "2033-12-10",
                    "closing_date": "2034-03-05",
                },
                self.TODAY,
            )
            is None
        )

    def test_inverted_pair_dropped(self):
        assert (
            normalize_record(
                {
                    "open_flag": 2,
                    "opening_date": "2027-04-11",
                    "closing_date": "2026-12-04",
                },
                self.TODAY,
            )
            is None
        )

    def test_no_dates_dropped(self):
        assert normalize_record({"open_flag": 2}, self.TODAY) is None
        assert (
            normalize_record(
                {"open_flag": 2, "opening_date": "soon", "closing_date": ""},
                self.TODAY,
            )
            is None
        )


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


class TestDeriveSeasonStatus:
    OPEN, CLOSE = "2026-12-04", "2027-04-11"

    @pytest.mark.parametrize(
        "today,expected",
        [
            (date(2026, 11, 17), STATUS_PRE_SEASON),  # before opening
            (date(2026, 12, 3), STATUS_PRE_SEASON),
            (date(2026, 12, 4), STATUS_OPEN),  # opening day
            (date(2027, 1, 15), STATUS_OPEN),
            (date(2027, 2, 24), STATUS_OPEN),  # 46 days before closing
            (date(2027, 2, 25), STATUS_CLOSING_SOON),  # 45 days before closing
            (date(2027, 4, 11), STATUS_CLOSING_SOON),  # closing day
            (date(2027, 4, 12), STATUS_POST_SEASON),  # after closing
        ],
    )
    def test_date_logic(self, today, expected):
        assert derive_season_status(self.OPEN, self.CLOSE, today) == expected

    def test_closing_soon_boundary_is_45_days(self):
        closing = date(2027, 4, 11)
        assert (
            derive_season_status(self.OPEN, self.CLOSE, closing - timedelta(days=45))
            == STATUS_CLOSING_SOON
        )
        assert (
            derive_season_status(self.OPEN, self.CLOSE, closing - timedelta(days=46))
            == STATUS_OPEN
        )

    def test_no_dates(self):
        assert derive_season_status(None, None, date(2026, 11, 17)) is None

    def test_reported_open_before_projected_date_is_open(self):
        # Opened early: the projected date is still ahead, the resort reports open
        assert (
            derive_season_status(
                "2026-11-20", "2027-03-28", date(2026, 11, 17), open_flag=1
            )
            == STATUS_OPEN
        )

    def test_weekends_only_counts_as_open(self):
        assert (
            derive_season_status(
                "2026-11-07", "2027-04-19", date(2026, 11, 17), open_flag=4
            )
            == STATUS_OPEN
        )

    def test_reported_open_near_closing_is_closing_soon(self):
        assert (
            derive_season_status(
                "2026-11-05", "2027-06-06", date(2027, 5, 1), open_flag=1
            )
            == STATUS_CLOSING_SOON
        )

    def test_reported_open_after_closing_date_is_post_season(self):
        assert (
            derive_season_status(
                "2026-11-05", "2027-04-01", date(2027, 4, 5), open_flag=1
            )
            == STATUS_POST_SEASON
        )

    def test_delayed_opening_is_not_shown_as_open(self):
        # Projected opening passed, resort still reports closed early in season
        assert (
            derive_season_status(
                "2026-11-14", "2027-04-11", date(2026, 11, 17), open_flag=2
            )
            == STATUS_PRE_SEASON
        )

    def test_closed_early_late_in_season_is_post_season(self):
        assert (
            derive_season_status(
                "2026-12-04", "2027-04-11", date(2027, 3, 20), open_flag=2
            )
            == STATUS_POST_SEASON
        )

    def test_temporarily_closed(self):
        assert (
            derive_season_status(
                "2026-06-19", "2026-12-01", date(2026, 11, 10), open_flag=3
            )
            == STATUS_TEMPORARILY_CLOSED
        )

    def test_only_closing_date(self):
        assert derive_season_status(None, "2027-04-11", date(2027, 1, 1)) is None
        assert (
            derive_season_status(None, "2027-04-11", date(2027, 4, 1))
            == STATUS_CLOSING_SOON
        )
        assert (
            derive_season_status(None, "2027-04-11", date(2027, 4, 12))
            == STATUS_POST_SEASON
        )

    def test_only_opening_date(self):
        assert (
            derive_season_status("2026-12-04", None, date(2026, 11, 17))
            == STATUS_PRE_SEASON
        )
        assert derive_season_status("2026-12-04", None, date(2027, 1, 1)) == STATUS_OPEN

    def test_southern_hemisphere_closed_for_season(self):
        assert (
            derive_season_status(
                "2026-06-13", "2026-10-04", date(2026, 11, 17), open_flag=2
            )
            == STATUS_POST_SEASON
        )


class TestResortToday:
    def test_uses_resort_timezone(self):
        # 02:00 UTC on Dec 4 is still Dec 3 in California
        now = datetime(2026, 12, 4, 2, 0, tzinfo=UTC)
        assert resort_today("America/Los_Angeles", now) == date(2026, 12, 3)
        assert resort_today("Europe/Zurich", now) == date(2026, 12, 4)

    def test_unknown_timezone_falls_back_to_utc(self):
        now = datetime(2026, 12, 4, 2, 0, tzinfo=UTC)
        assert resort_today("Not/AZone", now) == date(2026, 12, 4)
        assert resort_today(None, now) == date(2026, 12, 4)


# ---------------------------------------------------------------------------
# Cache entries and merging into resorts
# ---------------------------------------------------------------------------


class TestFreshEntries:
    def test_drops_old_and_malformed_entries(self):
        now = datetime(2026, 11, 17, tzinfo=UTC)
        cache = {
            "resorts": {
                "fresh": {"fetched_at": "2026-11-16T12:00:00+00:00"},
                "old": {"fetched_at": "2026-10-01T12:00:00+00:00"},
                "nodate": {},
                "bad": "x",
            }
        }
        assert set(fresh_entries(cache, now)) == {"fresh"}

    def test_handles_missing_or_bad_cache(self):
        assert fresh_entries(None) == {}
        assert fresh_entries({"resorts": []}) == {}


class TestApplySeasonDates:
    def test_fills_fields_for_resorts_with_data(self):
        entries = {
            "kirkwood": {
                "opening_date": "2099-12-04",
                "closing_date": "2100-04-11",
                "open_flag": 2,
                "fetched_at": "2026-11-17T00:00:00+00:00",
            }
        }
        out = apply_season_dates([_resort("kirkwood"), _resort("homewood")], entries)
        assert out[0].opening_date == "2099-12-04"
        assert out[0].closing_date == "2100-04-11"
        assert out[0].season_status == STATUS_PRE_SEASON
        assert out[0].season_dates_source == "onthesnow"
        # No data -> no dates, no status (never invented)
        assert out[1].opening_date is None
        assert out[1].season_status is None
        assert out[1].season_dates_source is None

    def test_does_not_mutate_input(self):
        resort = _resort()
        apply_season_dates(
            [resort], {"kirkwood": {"opening_date": "2026-12-04", "closing_date": None}}
        )
        assert resort.opening_date is None

    def test_empty_list(self):
        assert apply_season_dates([], {}) == []

    def test_season_fields_for_without_entry(self):
        assert season_fields_for(None, "UTC") == dict.fromkeys(SEASON_FIELDS)

    def test_scores_and_other_fields_untouched(self):
        resort = _resort()
        out = apply_season_dates(
            [resort], {"kirkwood": {"opening_date": "2026-12-04", "closing_date": None}}
        )[0]
        before = resort.model_dump(exclude=SEASON_FIELDS)
        after = out.model_dump(exclude=SEASON_FIELDS)
        assert before == after


class TestLoadSeasonDates:
    def _s3(self, payload):
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = json.dumps(payload).encode()
        s3.get_object.return_value = {"Body": body}
        return s3

    def test_loads_fresh_entries_and_caches(self):
        now = datetime.now(UTC).isoformat()
        s3 = self._s3(
            {"resorts": {"kirkwood": {"opening_date": "2026-12-04", "fetched_at": now}}}
        )
        entries = load_season_dates(s3, "bucket")
        assert set(entries) == {"kirkwood"}
        s3.get_object.assert_called_once_with(Bucket="bucket", Key=SEASON_DATES_S3_KEY)
        # Second call is served from the in-memory cache
        load_season_dates(s3, "bucket")
        assert s3.get_object.call_count == 1

    def test_missing_file_returns_empty(self):
        s3 = MagicMock()
        s3.get_object.side_effect = Exception("NoSuchKey")
        assert load_season_dates(s3, "bucket") == {}

    def test_no_bucket_returns_empty(self, monkeypatch):
        monkeypatch.delenv("WEBSITE_BUCKET", raising=False)
        s3 = MagicMock()
        assert load_season_dates(s3) == {}
        s3.get_object.assert_not_called()


class TestResortServiceNeverPersistsSeasonFields:
    def test_create_and_update_exclude_season_fields(self):
        from services.resort_service import ResortService

        table = MagicMock()
        service = ResortService(table)
        resort = _resort().model_copy(
            update={
                "opening_date": "2026-12-04",
                "closing_date": "2027-04-11",
                "season_status": STATUS_PRE_SEASON,
                "season_dates_source": "onthesnow",
            }
        )
        service.create_resort(resort)
        service.update_resort(resort)
        for call in table.put_item.call_args_list:
            item = call.kwargs["Item"]
            assert not (SEASON_FIELDS & set(item)), item.keys()


class TestMappingFile:
    """The committed resort_id -> OnTheSnow page mapping must be sane."""

    def test_mapping_is_valid(self):
        mapping = json.loads(
            (BACKEND / "src/services/onthesnow_season_pages.json").read_text()
        )["resorts"]
        catalog = json.loads((BACKEND / "data/resorts.json").read_text())["resorts"]
        catalog_ids = {r["resort_id"] for r in catalog}
        assert len(mapping) > 300
        for resort_id, entry in mapping.items():
            assert resort_id in catalog_ids, resort_id
            assert entry["url"].startswith("https://www.onthesnow."), entry
            assert entry["url"].endswith("/skireport"), entry
            assert isinstance(entry["uuid"], str) and entry["uuid"], entry

    @pytest.mark.parametrize(
        "resort_id",
        [
            "kirkwood",
            "sierra-at-tahoe",
            "homewood-mountain-resort",
            "palisades-tahoe",
            "heavenly",
            "northstar",
            "sugar-bowl",
        ],
    )
    def test_brief_sample_resorts_are_mapped(self, resort_id):
        mapping = json.loads(
            (BACKEND / "src/services/onthesnow_season_pages.json").read_text()
        )["resorts"]
        assert resort_id in mapping
