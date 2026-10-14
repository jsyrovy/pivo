import datetime as dt
import logging
import os
import re
import time
from typing import Optional

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Archive
from database.orm import engine
from robot.orm import OrmRobot

logger = logging.getLogger(__name__)


class Archivist(OrmRobot):
    def _main(self) -> None:
        user = "sejrik"
        key = os.environ["FEED_KEY"]
        feed = feedparser.parse(f"https://untappd.com/rss/user/{user}?key={key}")

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

        for record in records:
            if not is_record_in_db(record.id):
                logger.info("Saved to DB: %s", record)
                create_record_in_db(record)


def get_id(url: str) -> int:
    return int(url.rsplit("/", maxsplit=1)[-1])


def get_dt(struct: time.struct_time) -> dt.datetime:
    return dt.datetime.fromtimestamp(time.mktime(struct))


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


def is_record_in_db(id_: int) -> bool:
    stmt = select(Archive.id).where(Archive.id == id_)
    with Session(engine) as session:
        return bool(session.execute(stmt).first())


def create_record_in_db(record: Archive) -> None:
    with Session(engine) as session:
        session.add(record)
        session.commit()
