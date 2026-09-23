from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from untappd_pairing import fixtures, overrides, store
from utils import common
from utils.logging import configure_logging

logger = logging.getLogger(__name__)

# One-off: the tap-api parsers stopped leaking ABV, style and serving size into `brewery`, which is
# part of every pairing key. Moving the stored keys along keeps the pairings and annotations of these
# beers instead of pairing them from scratch under the new key. Maps (source, old brewery) to the
# brewery the fixed parsers produce for the same menu entry.
BREWERY_REWRITES: dict[tuple[str, str], str] = {
    ("ambasada", "6, 2% Sibeeria/Čierny Kameň"): "Sibeeria/Čierny Kameň",
    ("ambasada", "Fenetra, Potštejn, Rustical Wild Sour Ale, 0"): "Fenetra, Potštejn",
    ("ambasada", "Haksna, Ostrava, Stout s laktozou"): "Haksna, Ostrava",
    ("ambasada", "Roman, Východní Flandry, Belgian Fruit Ale, 0"): "Roman, Východní Flandry",
    ("ambasada", "Sibeeria/Herrenwald, Sour Ale w/ Raspberry"): "Sibeeria/Herrenwald",
    (
        "ambasada",
        "Van Honsebrouck, Ingelmunster, Západní Flandry, višňový Belgian Dark Strong ALE, 0",
    ): "Van Honsebrouck, Ingelmunster, Západní Flandry",
    (
        "ambasada",
        "piv. Van Honsebrouck, Ingelmunster, Západní Flandry, Tropical Fruit Ale, 0",
    ): "Van Honsebrouck, Ingelmunster, Západní Flandry",
    ("uzamastilu", "4.3% alc Loutkář"): "Loutkář",
    ("uzamastilu", "NZ Hazy Ale Klenot"): "Klenot",
    ("uzamastilu", "NZ Hazy IPA Klenot"): "Klenot",
    ("uzamastilu", "Pale Ale Brewnicorn"): "Brewnicorn",
    ("uzamastilu", "Pastry Sour Twinberg"): "Twinberg",
    ("uzamastilu", "Sour Madcat"): "Madcat",
}


def rewritten_key(key: str) -> str | None:
    source, brewery, name = key.split("::", 2)
    new_brewery = BREWERY_REWRITES.get((source, brewery))
    return None if new_brewery is None else store.beer_key(source, new_brewery, name)


def rewrite_keys(entries: dict[str, Any], label: str) -> dict[str, Any]:
    # Rebuilt in the original order, so a file that was never re-sorted (overrides.json) only changes
    # on the rewritten lines.
    result: dict[str, Any] = {}
    targets = set(entries)
    for key, value in entries.items():
        new_key = rewritten_key(key)
        if new_key is None:
            result[key] = value
        elif new_key in targets:
            logger.warning("%s: %s already exists, keeping %s as is", label, new_key, key)
            result[key] = value
        else:
            logger.info("%s: %s -> %s", label, key, new_key)
            targets.add(new_key)
            result[new_key] = value
    return result


def _rewrite_fixture_breweries(records: dict[str, Any]) -> None:
    # A fixture records the beer it was captured for, and replays match against that brewery.
    for key, record in records.items():
        if isinstance(record, dict) and isinstance(record.get("beer"), dict):
            record["beer"]["brewery"] = key.split("::", 2)[1]


def rewrite_files(pairings_path: Path, overrides_path: Path, fixtures_path: Path) -> None:
    pairings_data = common.load_json_dict(pairings_path)
    for section in ("pairings", "unmatched"):
        entries = rewrite_keys(pairings_data.get(section) or {}, f"{pairings_path.name}/{section}")
        pairings_data[section] = dict(sorted(entries.items()))
    common.atomic_write_json(pairings_path, pairings_data)

    common.atomic_write_json(overrides_path, rewrite_keys(common.load_json_dict(overrides_path), overrides_path.name))

    fixtures_data = common.load_json_dict(fixtures_path)
    records = dict(sorted(rewrite_keys(fixtures_data.get("fixtures") or {}, fixtures_path.name).items()))
    _rewrite_fixture_breweries(records)
    fixtures_data["fixtures"] = records
    common.atomic_write_json(fixtures_path, fixtures_data)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move pairing keys to the breweries the fixed parsers produce.")
    parser.add_argument("--pairings", type=Path, default=store.PAIRINGS_PATH, help="path to pairings.json")
    parser.add_argument("--overrides", type=Path, default=overrides.OVERRIDES_PATH, help="path to overrides.json")
    parser.add_argument("--fixtures", type=Path, default=fixtures.FIXTURES_PATH, help="path to fixtures.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv)
    rewrite_files(args.pairings, args.overrides, args.fixtures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
