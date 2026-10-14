import datetime as dt
import logging
import os
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Optional

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Archive
from database.orm import engine
from robot.orm import OrmRobot

if TYPE_CHECKING:
    import time

logger = logging.getLogger(__name__)


class Archivist(OrmRobot):
    def _main(self) -> None:
        user = "sejrik"
        key = os.environ["FEED_KEY"]
        feed = feedparser.parse(f"https://untappd.com/rss/user/{user}?key={key}")
        check_feed(feed)

        records = [
            Archive(
                id=get_id(entry.id),
                dt_utc=get_dt(entry.published_parsed),
                user=user,
                beer=get_beer(entry.title),
                brewery=get_brewery(entry.title),
                venue=get_venue(entry.title),
            )
            for entry in feed.entries
        ]

        existing = get_existing_ids([record.id for record in records])
        new_records = [record for record in records if record.id not in existing]
        for record in new_records:
            logger.info("Saved to DB: %s", record)
        create_records_in_db(new_records)
        logger.info("Feed has %d check-ins, %d new", len(records), len(new_records))


class FeedError(Exception):
    pass


def check_feed(feed: feedparser.FeedParserDict) -> None:
    # feedparser never raises: a dead key or a network error just yields an empty feed, which would
    # pass for "no new check-ins" forever. Redirects (3xx) are fine, feedparser reports their code.
    status = feed.get("status")
    if status is None or status >= HTTPStatus.BAD_REQUEST:
        msg = f"Untappd feed failed (HTTP {status}): {feed.get('bozo_exception')}"
        raise FeedError(msg)
    if feed.get("bozo") and not feed.entries:
        msg = f"Untappd feed is malformed: {feed.get('bozo_exception')}"
        raise FeedError(msg)


def get_id(url: str) -> int:
    return int(url.rsplit("/", maxsplit=1)[-1])


def get_dt(struct: time.struct_time) -> dt.datetime:
    # The feed's struct is UTC; mktime would read it as local time and skew it by the machine's offset.
    return dt.datetime(*struct[:6])


def get_regex_group(regex: str, text: str) -> str:
    if match := re.search(regex, text, re.IGNORECASE):
        return match.group(1).strip()

    raise ValueError(f"Regex `{regex}` not found in `{text}`.")


def get_optional_regex_group(regex: str, text: str) -> str | None:
    try:
        return get_regex_group(regex, text)
    except ValueError:
        return None


def get_beer(text: str) -> str:
    return get_regex_group(r"is drinking an? (.*) by ", text)


def get_brewery(text: str) -> str:
    if "Untappd at Home" in text:
        text = text.replace("Untappd at Home", "")

    regex = r" by (.*)"
    regex_at = " at "

    if regex_at in text:
        regex += regex_at

    return get_regex_group(regex, text)


def get_venue(text: str) -> str | None:
    return get_optional_regex_group(r" at (.*)", text)


def get_existing_ids(ids: list[int]) -> set[int]:
    stmt = select(Archive.id).where(Archive.id.in_(ids))
    with Session(engine) as session:
        return set(session.execute(stmt).scalars())


def create_records_in_db(records: list[Archive]) -> None:
    with Session(engine) as session:
        session.add_all(records)
        session.commit()
