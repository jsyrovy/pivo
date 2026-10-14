import datetime as dt
import logging
import os
import time
from time import struct_time
from unittest import mock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from archivist import (
    Archivist,
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


def _rss(check_in_ids):
    items = "".join(
        f"<item><title>User is drinking a Beer by Brewery at Venue</title>"
        f"<guid>https://untappd.com/user/sejrik/checkin/{id_}</guid>"
        f"<pubDate>Wed, 01 Jan 2020 00:00:00 +0000</pubDate></item>"
        for id_ in check_in_ids
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>'


def _run(body):
    with (
        mock.patch.dict(os.environ, {"FEED_KEY": "key"}),
        mock.patch("utils.common.download_page", return_value=body) as download_mock,
        mock.patch("robot.orm.dump") as dump_mock,
    ):
        Archivist().run()
    return download_mock, dump_mock


def test_run():
    download_mock, _ = _run(_rss([666]))

    download_mock.assert_called_once_with("https://untappd.com/rss/user/sejrik?key=key")

    stmt = select(Archive).where(Archive.id == 666)
    with Session(engine) as session:
        record = session.execute(stmt).scalar_one()

    assert record.beer == "Beer"
    assert record.dt_utc == dt.datetime(2020, 1, 1, 0, 0, 0)


def test_run_skips_known_check_ins_and_logs_counts(caplog):
    with caplog.at_level(logging.INFO):
        _run(_rss([1, 666]))

    assert "Feed has 2 check-ins, 1 new" in caplog.text
    assert caplog.text.count("Saved to DB") == 1


def test_run_rejects_malformed_feed():
    with pytest.raises(ValueError, match="malformed"):
        _run("<html>Not a feed</html")
