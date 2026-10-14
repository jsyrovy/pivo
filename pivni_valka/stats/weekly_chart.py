import datetime as dt
from collections import OrderedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import utils.user
from database.models import PivniValka
from database.orm import engine
from pivni_valka.stats.common import ChartData, ChartDataset


def _get_week_stats() -> dict[str, dict[str, int]]:
    since = dt.date.today() - dt.timedelta(weeks=12)
    result: dict[str, dict[str, int]] = {}
    stmt = (
        select(
            func.strftime("%Y-%W", PivniValka.date).label("week"),
            PivniValka.user,
            func.sum(PivniValka.unique_beers),
        )
        .where(PivniValka.date >= since)
        .group_by("week", "user")
        .order_by("week")
    )

    with Session(engine) as session:
        stats = session.execute(stmt).all()

    for week, user_name, beers in stats:
        result.setdefault(user_name, OrderedDict())[week] = beers

    return result


def get_chart_data() -> ChartData:
    datasets = []
    labels: list[str] = []

    for user_name, stats in _get_week_stats().items():
        if user_name not in utils.user.VISIBLE_USER_NAMES:
            continue

        labels = labels or list(stats.keys())
        user = utils.user.get(user_name)
        datasets.append(ChartDataset(user.name, list(stats.values()), user.color))

    return ChartData(labels, datasets)
