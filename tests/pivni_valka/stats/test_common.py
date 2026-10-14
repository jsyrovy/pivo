import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import PivniValka
from database.orm import engine
from pivni_valka.stats.common import (
    get_total_unique_beers,
    get_unique_beers,
    get_unique_beers_before,
    save_daily_stats,
)


def test_get_total_unique_beers():
    assert get_total_unique_beers() == {
        "sejrik": 11,
        "mencik2": 22,
        "Indi51": 33,
        "karolina_matukova_7117": 44,
        "ominar": 0,
    }


def test_get_unique_beers():
    assert get_unique_beers("sejrik") == "11"
    assert get_unique_beers("sejrik", days=1) == "10"
    assert get_unique_beers("sejrik", days=1, formatted=True) == "+10"
    assert get_unique_beers("ominar") == "0"
    assert get_unique_beers("ominar", formatted=True) == "0"


def test_get_unique_beers_before():
    assert get_unique_beers_before("sejrik", dt.date.today()) == 11
    assert get_unique_beers_before("sejrik", dt.date(2022, 1, 2)) == 0
    assert get_unique_beers_before("sejrik", dt.date(2022, 1, 3)) == 1


def test_save_daily_stats():
    def _get_count(_date, _user_name):
        stmt = select(func.sum(PivniValka.unique_beers)).where(PivniValka.date == _date, PivniValka.user == _user_name)
        with Session(engine) as session:
            return session.execute(stmt).scalar_one()

    date = dt.date.today()
    user_name = "tester"

    save_daily_stats(date, user_name, 1)
    assert _get_count(date, user_name) == 1

    save_daily_stats(date, user_name, 2)
    assert _get_count(date, user_name) == 2
