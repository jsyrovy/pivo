import json
from unittest import mock

from utils.common import (
    USER_AGENTS,
    download_page,
    get_profile_url,
    get_random_user_agent,
    get_template,
    is_test,
    post_json,
    random_sleep,
    write_json_if_changed,
)


def test_get_random_user_agent():
    assert get_random_user_agent() in USER_AGENTS


def test_download_page():
    with mock.patch("httpx.Client.get") as get_mock:
        type(get_mock.return_value).text = mock.PropertyMock(return_value="hi")
        assert download_page("") == "hi"


def test_download_page_merges_extra_headers():
    with mock.patch("utils.common.httpx.Client") as client_cls:
        client_instance = client_cls.return_value.__enter__.return_value
        client_instance.get.return_value.text = "hi"
        download_page("", extra_headers={"X-Custom": "yes"})

    headers = client_cls.call_args.kwargs["headers"]
    assert headers["X-Custom"] == "yes"
    assert "User-Agent" in headers


def test_post_json():
    with mock.patch("httpx.Client.post") as post_mock:
        type(post_mock.return_value).json = mock.Mock(return_value={"hits": []})
        assert post_json("", {"params": "query=x"}) == {"hits": []}
        assert post_mock.call_args.kwargs["json"] == {"params": "query=x"}


def test_post_json_merges_extra_headers():
    with mock.patch("utils.common.httpx.Client") as client_cls:
        client_instance = client_cls.return_value.__enter__.return_value
        client_instance.post.return_value.json.return_value = {}
        post_json("", {}, extra_headers={"X-Custom": "yes"})

    headers = client_cls.call_args.kwargs["headers"]
    assert headers["X-Custom"] == "yes"
    assert "User-Agent" in headers


def test_get_template():
    name = "pivni-valka.html"
    assert get_template(name).name == name


def test_random_sleep():
    with mock.patch("utils.common.time.sleep") as sleep_mock:
        random_sleep()
        sleep_mock.assert_called_once()


def test_get_profile_url():
    assert get_profile_url("Peter") == "https://untappd.com/user/Peter"


def test_is_test():
    assert is_test()


def test_write_json_if_changed_creates_missing_file(tmp_path):
    path = tmp_path / "sub" / "data.json"
    assert write_json_if_changed(path, {"generated_at": "t1", "items": [1]})
    assert json.loads(path.read_text()) == {"generated_at": "t1", "items": [1]}


def test_write_json_if_changed_keeps_file_when_only_stamp_differs(tmp_path):
    path = tmp_path / "data.json"
    write_json_if_changed(path, {"generated_at": "t1", "items": (1, 2)})
    before = path.read_text()
    assert not write_json_if_changed(path, {"generated_at": "t2", "items": (1, 2)})
    assert path.read_text() == before


def test_write_json_if_changed_rewrites_when_content_differs(tmp_path):
    path = tmp_path / "data.json"
    write_json_if_changed(path, {"generated_at": "t1", "items": [1]})
    assert write_json_if_changed(path, {"generated_at": "t2", "items": [2]})
    assert json.loads(path.read_text()) == {"generated_at": "t2", "items": [2]}


def test_write_json_if_changed_creates_file_even_when_payload_is_only_the_stamp(tmp_path):
    path = tmp_path / "data.json"
    assert write_json_if_changed(path, {"generated_at": "t1"})
    assert path.exists()
