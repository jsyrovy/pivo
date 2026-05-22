from pathlib import Path

from utils import common

OVERRIDES_PATH = Path("untappd_pairing/overrides.json")


def load(path: Path = OVERRIDES_PATH) -> dict[str, str]:
    return {str(k): str(v) for k, v in common.load_json_dict(path).items()}
