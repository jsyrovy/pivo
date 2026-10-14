import datetime as dt
import logging
import os
import time
from time import struct_time
from unittest import mock
from unittest.mock import MagicMock

import feedparser
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from archivist import (
    Archivist,
    FeedError,
    check_feed,
    create_records_in_db,
    get_beer,
    get_brewery,
    get_dt,
    get_existing_ids,
    get_id,
    get_optional_regex_group,
    get_regex_group,
    get_venue,
)
from database.models import Archive
from database.orm import engine

SOURCES = (
    {
        "text": "Jiří S. is drinking a Denali NEIPA by  Bad Flash at U Toulavé pípy",
        "beer": "Denali NEIPA",
        "brewery": "Bad Flash",
        "venue": "U Toulavé pípy",
    },
    {
        "text": "Jiří S. is drinking an Arnoštova Hořká 10 by  Pardubický pivovar at Untappd at Home",
        "beer": "Arnoštova Hořká 10",
        "brewery": "Pardubický pivovar",
        "venue": "Untappd at Home",
    },
    {
        "text": "Jiří S. is drinking a Welzl 16 IPA by  Pivovar Zábřeh",
        "beer": "Welzl 16 IPA",
        "brewery": "Pivovar Zábřeh",
        "venue": None,
    },
)


def test_get_dt():
    assert get_dt(struct_time((2020, 1, 1, 0, 0, 0, 0, 0, 0))) == dt.datetime(2020, 1, 1, 0, 0, 0)


def test_get_dt_ignores_machine_timezone(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Prague")
    time.tzset()
    try:
        assert get_dt(struct_time((2020, 7, 1, 12, 0, 0, 0, 0, 0))) == dt.datetime(2020, 7, 1, 12, 0, 0)
    finally:
        monkeypatch.undo()
        time.tzset()


def _feed(*, entries=(), status=200, bozo=False, bozo_exception=None):
    feed = feedparser.FeedParserDict(entries=list(entries), bozo=bozo)
    if status is not None:
        feed["status"] = status
    if bozo_exception is not None:
        feed["bozo_exception"] = bozo_exception
    return feed


def test_check_feed_accepts_ok_and_redirect():
    check_feed(_feed(status=200))
    check_feed(_feed(status=301))


def test_check_feed_accepts_bozo_feed_with_entries():
    check_feed(_feed(entries=[MagicMock()], bozo=True, bozo_exception=ValueError("encoding")))


@pytest.mark.parametrize("status", [403, 500])
def test_check_feed_rejects_http_errors(status):
    with pytest.raises(FeedError) as excinfo:
        check_feed(_feed(status=status))
    assert f"HTTP {status}" in str(excinfo.value)


def test_check_feed_rejects_network_failure():
    with pytest.raises(FeedError) as excinfo:
        check_feed(_feed(status=None, bozo=True, bozo_exception=OSError("no route")))
    assert "no route" in str(excinfo.value)


def test_check_feed_rejects_malformed_empty_feed():
    with pytest.raises(FeedError) as excinfo:
        check_feed(_feed(bozo=True, bozo_exception=ValueError("not xml")))
    assert "malformed" in str(excinfo.value)


def test_get_beer():
    for source in SOURCES:
        assert get_beer(source["text"]) == source["beer"]


def test_get_brewery():
    for source in SOURCES:
        assert get_brewery(source["text"]) == source["brewery"]


def test_get_venue():
    for source in SOURCES:
        assert get_venue(source["text"]) == source["venue"]


def test_get_id():
    assert get_id("https://untappd.com/user/sejrik/checkin/1252442889") == 1252442889


def test_get_regex_group():
    assert get_regex_group(r"select (.*)", "select this") == "this"

    with pytest.raises(ValueError):
        get_regex_group(r"yes", "nope")


def test_get_optional_regex_group():
    assert get_optional_regex_group(r"select (.*)", "select this") == "this"
    assert get_optional_regex_group(r"yes", "nope") is None


def test_get_existing_ids():
    assert get_existing_ids([1, 10]) == {1}
    assert get_existing_ids([]) == set()


def test_create_records_in_db():
    id_ = 100
    user = "user"
    beer = "pivo"
    brewery = "pivovar"
    venue = "venue"

    create_records_in_db(
        [
            Archive(
                id=id_,
                dt_utc=dt.datetime.now(),
                user=user,
                beer=beer,
                brewery=brewery,
                venue=venue,
            ),
        ],
    )

    stmt = select(Archive).where(
        Archive.id == id_,
        Archive.user == user,
        Archive.beer == beer,
        Archive.brewery == brewery,
        Archive.venue == venue,
    )
    with Session(engine) as session:
        assert session.execute(stmt).scalar_one()


def test_run():
    entry_mock = MagicMock()
    entry_mock.id = "666"
    entry_mock.published_parsed = struct_time((2020, 1, 1, 0, 0, 0, 0, 0, 0))
    entry_mock.title = "User is drinking a Beer by Brewery at Venue"

    feed_mock = _feed(entries=[entry_mock])

    with (
        mock.patch.dict(os.environ, {"FEED_KEY": "key"}),
        mock.patch("feedparser.parse", return_value=feed_mock) as mock_parse,
        mock.patch("robot.orm.dump"),
    ):
        Archivist().run()

    mock_parse.assert_called_once_with("https://untappd.com/rss/user/sejrik?key=key")

    stmt = select(Archive).where(Archive.id == 666)
    with Session(engine) as session:
        record = session.execute(stmt).scalar_one()

    assert record.id == 666
    assert record.dt_utc == dt.datetime(2020, 1, 1, 0, 0, 0)
    assert record.user == "sejrik"
    assert record.beer == "Beer"
    assert record.brewery == "Brewery"
    assert record.venue == "Venue"


def test_run_skips_known_check_ins_and_logs_counts(caplog):
    entry_mock = MagicMock()
    entry_mock.id = "https://untappd.com/user/sejrik/checkin/1"
    entry_mock.published_parsed = struct_time((2020, 1, 1, 0, 0, 0, 0, 0, 0))
    entry_mock.title = "User is drinking a Beer by Brewery at Venue"

    with (
        mock.patch.dict(os.environ, {"FEED_KEY": "key"}),
        mock.patch("feedparser.parse", return_value=_feed(entries=[entry_mock])),
        mock.patch("robot.orm.dump"),
        caplog.at_level(logging.INFO),
    ):
        Archivist().run()

    assert "Feed has 1 check-ins, 0 new" in caplog.text
    assert "Saved to DB" not in caplog.text


def test_run_fails_without_dumping_when_feed_fails():
    with (
        mock.patch.dict(os.environ, {"FEED_KEY": "key"}),
        mock.patch("feedparser.parse", return_value=_feed(status=403)),
        mock.patch("robot.orm.dump") as dump_mock,
        pytest.raises(FeedError),
    ):
        Archivist().run()

    dump_mock.assert_not_called()
