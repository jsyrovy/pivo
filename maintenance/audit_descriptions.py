from __future__ import annotations

import argparse
import logging
from pathlib import Path

from untappd_pairing import describe, store
from utils.logging import configure_logging

logger = logging.getLogger(__name__)


def find_suspect_descriptions(pairings_store: store.PairingsStore) -> list[tuple[str, str, str]]:
    suspects = []
    for key in sorted(pairings_store.pairings):
        description = pairings_store.get_description(key)
        if description is None:
            continue
        reason = describe.rejection_reason(description)
        if reason is not None:
            suspects.append((key, reason, description))
    return suspects


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report AI beer descriptions that fail the plausibility check.")
    parser.add_argument("--drop", action="store_true", help="remove the offending descriptions from the store")
    parser.add_argument("--path", type=Path, default=store.PAIRINGS_PATH, help="path to pairings.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv)
    pairings_store = store.PairingsStore.load(args.path)
    suspects = find_suspect_descriptions(pairings_store)
    described = sum(1 for key in pairings_store.pairings if pairings_store.get_description(key))

    if not suspects:
        logger.info("All %d descriptions look fine", described)
        return 0

    for key, reason, description in suspects:
        logger.warning("%s (%s): %s", key, reason, description)

    if not args.drop:
        logger.warning("%d of %d descriptions are suspect; rerun with --drop to remove them", len(suspects), described)
        return 1

    for key, _reason, _description in suspects:
        pairings_store.clear_description(key)
    pairings_store.save(args.path)
    # clear_description leaves no cooldown marker, so the next pairing run regenerates these.
    logger.info("Dropped %d descriptions from %s", len(suspects), args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
