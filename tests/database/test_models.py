import datetime as dt

from database.models import Archive, PivniValka


def test_pivni_valka_repr():
    pivni_valka = PivniValka(
        id=1,
        date=dt.datetime(2023, 1, 2, 12, 11, 10, 9),
        user="user",
        unique_beers=5,
    )
    assert (
        repr(pivni_valka)
        == "PivniValka(id=1, date=datetime.datetime(2023, 1, 2, 12, 11, 10, 9), user='user', unique_beers=5)"
    )


def test_archive_repr():
    archive = Archive(
        id=1,
        dt_utc=dt.datetime(2023, 1, 2, 12, 11, 10, 9),
        user="user",
        beer="beer",
        brewery="brewery",
        venue="venue",
    )
    assert (
        repr(archive)
        == "Archive(id=1, dt_utc=datetime.datetime(2023, 1, 2, 12, 11, 10, 9), user='user', beer='beer', brewery='brewery', venue='venue')"  # noqa: E501
    )
