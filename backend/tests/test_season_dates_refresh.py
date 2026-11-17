"""Tests for the season dates refresh Lambda (handlers/season_dates_refresh.py)."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

with patch("boto3.client"):
    from handlers import season_dates_refresh as refresh
    from handlers.season_dates_refresh import (
        load_mapping,
        season_dates_refresh_handler,
    )

from services.season_dates import SEASON_DATES_S3_KEY

MAPPING = {
    "kirkwood": {
        "url": "https://www.onthesnow.com/california/kirkwood/skireport",
        "uuid": "201",
    },
    "sierra-at-tahoe": {
        "url": "https://www.onthesnow.com/california/sierra-at-tahoe/skireport",
        "uuid": "362",
    },
    "zermatt": {
        "url": "https://www.onthesnow.co.uk/valais/zermatt/skireport",
        "uuid": "500",
    },
    "ghost-town": {
        "url": "https://www.onthesnow.com/vermont/ghost/skireport",
        "uuid": "666",
    },
}

PAGES = {
    # Kirkwood's page also carries Sierra-at-Tahoe (a neighbour)
    MAPPING["kirkwood"]["url"]: {
        "201": {
            "open_flag": 2,
            "opening_date": "2026-12-04",
            "closing_date": "2027-04-11",
        },
        "362": {
            "open_flag": 2,
            "opening_date": "2026-12-06",
            "closing_date": "2027-03-21",
        },
    },
    MAPPING["sierra-at-tahoe"]["url"]: {
        "362": {
            "open_flag": 2,
            "opening_date": "2026-12-06",
            "closing_date": "2027-03-21",
        },
    },
    MAPPING["zermatt"]["url"]: {
        "500": {
            "open_flag": 1,
            "opening_date": "2026-06-20",
            "closing_date": "2027-05-02",
        },
    },
    MAPPING["ghost-town"]["url"]: {
        "666": {
            "open_flag": 6,
            "opening_date": "2033-12-10",
            "closing_date": "2034-03-05",
        },
    },
}


def _context(remaining_ms=600000):
    ctx = Mock()
    ctx.get_remaining_time_in_millis.return_value = remaining_ms
    return ctx


@pytest.fixture
def s3():
    client = MagicMock()
    client.get_object.side_effect = Exception("NoSuchKey")
    with patch.object(refresh, "s3_client", client):
        yield client


@pytest.fixture
def env():
    fetched = []

    def fake_fetch(session, url):
        fetched.append(url)
        if url not in PAGES:
            raise RuntimeError("404")
        return PAGES[url]

    with (
        patch.object(refresh, "load_mapping", return_value=dict(MAPPING)),
        patch.object(refresh, "fetch_page", side_effect=fake_fetch),
        patch.object(refresh, "BATCH_DELAY_SECONDS", 0),
        patch.object(refresh, "CONCURRENCY", 1),
    ):
        yield fetched


def _written(s3) -> dict:
    kwargs = s3.put_object.call_args.kwargs
    assert kwargs["Key"] == SEASON_DATES_S3_KEY
    return json.loads(kwargs["Body"].decode())


def test_refresh_writes_dates_for_mapped_resorts(s3, env):
    result = season_dates_refresh_handler({}, _context())
    assert result["statusCode"] == 200
    out = _written(s3)
    assert out["source"] == "onthesnow"
    assert out["resorts"]["kirkwood"]["opening_date"] == "2026-12-04"
    assert out["resorts"]["kirkwood"]["closing_date"] == "2027-04-11"
    assert out["resorts"]["kirkwood"]["source_url"] == MAPPING["kirkwood"]["url"]
    assert out["resorts"]["zermatt"]["open_flag"] == 1
    # No-report resort gets no entry at all
    assert "ghost-town" not in out["resorts"]
    assert set(out["last_attempted"]) == set(MAPPING)


def test_neighbour_records_save_page_fetches(s3, env):
    result = season_dates_refresh_handler({}, _context())
    out = _written(s3)
    # Sierra-at-Tahoe came with Kirkwood's page; its own page isn't fetched
    assert out["resorts"]["sierra-at-tahoe"]["opening_date"] == "2026-12-06"
    assert env == [
        MAPPING["kirkwood"]["url"],
        MAPPING["zermatt"]["url"],
        MAPPING["ghost-town"]["url"],
    ]
    assert json.loads(result["body"])["stats"]["pages_fetched"] == 3


def test_fetch_errors_keep_previous_entries(s3, env):
    now = datetime.now(UTC).isoformat()
    previous = {
        "resorts": {
            "zermatt": {
                "opening_date": "2026-06-20",
                "closing_date": "2027-05-02",
                "open_flag": 1,
                "fetched_at": now,
            }
        },
        "last_attempted": {},
    }
    body = MagicMock()
    body.read.return_value = json.dumps(previous).encode()
    s3.get_object.side_effect = None
    s3.get_object.return_value = {"Body": body}

    with patch.object(refresh, "fetch_page", side_effect=RuntimeError("boom")):
        result = season_dates_refresh_handler({}, _context())

    stats = json.loads(result["body"])["stats"]
    assert stats["page_errors"] == len(MAPPING)
    out = _written(s3)
    assert out["resorts"]["zermatt"]["opening_date"] == "2026-06-20"


def test_stale_previous_entries_are_dropped(s3, env):
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    previous = {
        "resorts": {"zermatt": {"opening_date": "2026-06-20", "fetched_at": old}}
    }
    body = MagicMock()
    body.read.return_value = json.dumps(previous).encode()
    s3.get_object.side_effect = None
    s3.get_object.return_value = {"Body": body}

    with patch.object(refresh, "fetch_page", side_effect=RuntimeError("boom")):
        season_dates_refresh_handler({}, _context())
    assert "zermatt" not in _written(s3)["resorts"]


def test_entries_dropped_when_source_no_longer_has_dates(s3, env):
    now = datetime.now(UTC).isoformat()
    previous = {
        "resorts": {
            "ghost-town": {
                "opening_date": "2026-12-10",
                "closing_date": "2027-03-05",
                "fetched_at": now,
            }
        }
    }
    body = MagicMock()
    body.read.return_value = json.dumps(previous).encode()
    s3.get_object.side_effect = None
    s3.get_object.return_value = {"Body": body}

    stats = json.loads(season_dates_refresh_handler({}, _context())["body"])["stats"]
    assert "ghost-town" not in _written(s3)["resorts"]
    assert stats["resorts_without_dates"] == 1


def test_graceful_timeout_stops_fetching(s3, env):
    result = season_dates_refresh_handler({}, _context(remaining_ms=1000))
    stats = json.loads(result["body"])["stats"]
    assert stats["timeout_graceful"] is True
    assert stats["pages_fetched"] == 0
    assert env == []
    s3.put_object.assert_called_once()


def test_least_recently_attempted_first(s3, env):
    previous = {
        "resorts": {},
        "last_attempted": {
            "kirkwood": "2026-11-17T00:00:00+00:00",
            "sierra-at-tahoe": "2026-11-17T00:00:00+00:00",
            "ghost-town": "2026-11-17T00:00:00+00:00",
        },
    }
    body = MagicMock()
    body.read.return_value = json.dumps(previous).encode()
    s3.get_object.side_effect = None
    s3.get_object.return_value = {"Body": body}

    season_dates_refresh_handler({}, _context())
    # zermatt was never attempted, so it goes first
    assert env[0] == MAPPING["zermatt"]["url"]


def test_committed_mapping_loads():
    mapping = load_mapping()
    assert "kirkwood" in mapping
    assert all(m["url"] and m["uuid"] for m in mapping.values())
