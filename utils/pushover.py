import os

import httpx

from utils.common import TIMEOUT

MAX_MESSAGE_LENGTH = 1024


def _chunk_message(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.split("\n"):
        added = len(line) + (1 if current else 0)
        if current and current_len + added > max_len:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += added
    if current:
        chunks.append("\n".join(current))
    return chunks


def send_notification(text: str) -> None:
    token = os.environ.get("PUSHOVER_TOKEN")
    user_key = os.environ.get("PUSHOVER_USER_KEY")

    if not token or not user_key:
        raise OSError("PUSHOVER_TOKEN or PUSHOVER_USER_KEY is not set in environment variables.")

    for chunk in _chunk_message(text):
        r = httpx.post(
            "https://api.pushover.net:443/1/messages.json",
            json={
                "token": token,
                "user": user_key,
                "message": chunk,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
