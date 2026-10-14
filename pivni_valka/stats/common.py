import datetime as dt  # noqa: TC003
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import PivniValka
from database.orm import engine


@dataclass
class ChartDataset:
    label: str
    data: list[int]
    color: str


@dataclass
class ChartData:
    labels: list[str]
    datasets: list[ChartDataset]


def get_total_unique_beers() -> dict[str, int]:
    stmt = select(PivniValka.user, func.sum(PivniValka.unique_beers)).group_by(PivniValka.user)
    with Session(engine) as session:
        return {user: count for user, count in session.execute(stmt).all()}  # noqa: C416


def get_unique_beers(user_name: str, days: int | None = None, formatted: bool = False) -> str:
    stmt = select(PivniValka.unique_beers).where(PivniValka.user == user_name).order_by(PivniValka.date.desc())

    if days:
        stmt = stmt.limit(days)

    with Session(engine) as session:
        values = session.execute(stmt).scalars().all()

    beers = sum(values)

    if formatted:
        return f"+{beers}" if beers else str(beers)

    return str(beers)


def get_unique_beers_before(user_name: str, before: dt.date) -> int:
    stmt = select(func.sum(PivniValka.unique_beers)).where(PivniValka.user == user_name, PivniValka.date < before)
    with Session(engine) as session:
        return session.execute(stmt).scalar_one()


def save_daily_stats(date: dt.date, user_name: str, count: int) -> None:
    select_stmt = select(PivniValka).where(PivniValka.date == date, PivniValka.user == user_name)
    with Session(engine) as session:
        record = session.execute(select_stmt).scalar_one_or_none()

        if record:
            record.unique_beers = count
        else:
            session.add(PivniValka(date=date, user=user_name, unique_beers=count))

        session.commit()
