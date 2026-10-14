import logging
import os


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Echoing every statement buries the useful lines in CI logs; LOG_SQL=1 brings it back for debugging.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if os.environ.get("LOG_SQL") else logging.WARNING)
