import os
from unittest import mock

import pytest

from utils.pushover import MAX_MESSAGE_LENGTH, _chunk_message, send_notification


@pytest.fixture(name="os_environ")
def fixture_os_environ():
    return mock.patch.dict(os.environ, {"PUSHOVER_TOKEN": "token", "PUSHOVER_USER_KEY": "key"})


def test_send_notification(os_environ):
    with os_environ, mock.patch("httpx.post") as post_mock:
        send_notification("test")

    post_mock.assert_called_once()


def test_send_notification_without_evn_variables():
    with pytest.raises(OSError):
        send_notification("test")


def test_send_notification_splits_long_messages(os_environ):
    long_message = "\n".join([f"- line {i} aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" for i in range(40)])
    assert len(long_message) > MAX_MESSAGE_LENGTH

    with os_environ, mock.patch("httpx.post") as post_mock:
        send_notification(long_message)

    assert post_mock.call_count > 1
    for call in post_mock.call_args_list:
        assert len(call.kwargs["json"]["message"]) <= MAX_MESSAGE_LENGTH


def test_chunk_message_returns_input_unchanged_when_short():
    assert _chunk_message("short message") == ["short message"]


def test_chunk_message_splits_on_newline_boundaries():
    text = "\n".join([f"line {i}" for i in range(10)])
    chunks = _chunk_message(text, max_len=30)
    for chunk in chunks:
        assert len(chunk) <= 30
    assert "\n".join(chunks) == text
