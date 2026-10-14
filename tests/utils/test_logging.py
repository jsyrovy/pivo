import logging

import pytest

from utils.logging import configure_logging


@pytest.fixture(autouse=True)
def _restore_sql_logger_level():
    sql_logger = logging.getLogger("sqlalchemy.engine")
    level = sql_logger.level
    yield
    sql_logger.setLevel(level)


def test_sql_statements_are_not_logged_by_default(monkeypatch):
    monkeypatch.delenv("LOG_SQL", raising=False)
    configure_logging()
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING


def test_log_sql_env_enables_statement_logging(monkeypatch):
    monkeypatch.setenv("LOG_SQL", "1")
    configure_logging()
    assert logging.getLogger("sqlalchemy.engine").level == logging.INFO
