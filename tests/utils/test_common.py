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
