from unittest import mock

import jinja2
import pytest

import utils.user
from pivni_valka import PivniValka
from robot.base import Args

USER_PROFILE = """ \
<html>
  <body>
    <div class="stats">
      <a
        href="/user/test"
        class="track-click"
        data-track="profile"
        data-href=":stats/general"
      >
        <span class="stat">777</span>
        <span class="title">Total</span> </a
      ><a
        href="/user/test/beers"
        class="track-click"
        data-track="profile"
        data-href=":stats/beerhistory"
      >
        <span class="stat">{unique_beers_count}</span>
        <span class="title">Unique</span> </a
      ><a
        href="/user/test/badges"
        class="track-click"
        data-track="profile"
        data-href=":stats/badges"
      >
        <span class="stat">555</span>
        <span class="title">Badges</span> </a
      ><a
        href="/user/test/friends"
        class="track-click"
        data-track="profile"
        data-href=":stats/friends"
      >
        <span class="stat">0</span>
        <span class="title">Friends</span>
      </a>
    </div>
  </body>
</html>
"""


def test_parse_unique_beers_count():
    user_profile = USER_PROFILE.format(unique_beers_count="1,234")

    assert PivniValka().parse_unique_beers_count(user_profile) == 1234


def test_parse_unique_beers_count_with_invalid_user_profile():
    user_profile = "<html></html>"

    with pytest.raises(ValueError) as excinfo:
        PivniValka().parse_unique_beers_count(user_profile)

    assert str(excinfo.value) == "Cannot parse user profile."


def test_get_unique_beers_count_publish():
    pv = PivniValka()
    pv._args = Args(publish=True)
    result = pv.get_unique_beers_count()
    assert result == {}


def test_get_unique_beers_count_local():
    pv = PivniValka()
    pv._args = Args(local=True)
    result = pv.get_unique_beers_count()

    for user_name in utils.user.USER_NAMES:
        assert user_name in result
        assert isinstance(result[user_name], int)


def test_get_unique_beers_count_download():
    user_profile = USER_PROFILE.format(unique_beers_count="500")

    with (
        mock.patch("pivni_valka.download_page", return_value=user_profile),
        mock.patch("pivni_valka.random_sleep"),
    ):
        pv = PivniValka()
        pv._args = Args()
        result = pv.get_unique_beers_count()

    for user_name in utils.user.USER_NAMES:
        assert result[user_name] == 500


def test_get_page():
    template = jinja2.Template("Hello {{ name }}!")
    result = PivniValka.get_page(template, name="World")
    assert result == "Hello World!"


def test_save_daily_stats_db_empty():
    result = PivniValka.save_daily_stats_db({})
    assert result == []


def test_save_daily_stats_db():
    unique_beers_count = {}
    for user_name in utils.user.USER_NAMES:
        unique_beers_count[user_name] = 100

    result = PivniValka.save_daily_stats_db(unique_beers_count)

    assert isinstance(result, list)
    for user_name in result:
        assert user_name in utils.user.USER_NAMES


def test_get_yesterday_status_empty():
    result = PivniValka.get_yesterday_status([])
    assert result == ""


def test_get_yesterday_status():
    result = PivniValka.get_yesterday_status(["sejrik"])
    assert "<b>Jirka</b>" in result
    assert "vypil" in result
    assert "<b>Včera:</b>" in result
    assert "<b>Celkem:</b>" in result
    assert 'href="https://pivo.jsyrovy.cz/pivni-valka"' in result


def test_get_grid_template_areas():
    result = PivniValka.get_grid_template_areas()
    assert len(result) == 3
    assert "item-total-chart" in result[1]
    assert "item-weekly-chart" in result[2]

    for area in result:
        assert area.startswith('"')
        assert area.endswith('"')


def test_get_mobile_grid_template_areas():
    result = PivniValka.get_mobile_grid_template_areas()
    assert '"item-total-chart"' in result
    assert '"item-weekly-chart"' in result

    for user_name in utils.user.VISIBLE_USER_NAMES:
        assert f'"item-{user_name}"' in result


def test_main_notificationless(tmp_path):
    pv = PivniValka()
    pv._args = Args(notificationless=True)

    output_dir = tmp_path / "pivni-valka"
    output_dir.mkdir()
    index_html = output_dir / "index.html"

    mock_template = jinja2.Template("rendered")

    with (
        mock.patch.object(pv, "get_unique_beers_count", return_value={}),
        mock.patch.object(pv, "save_daily_stats_db", return_value=[]),
        mock.patch("pivni_valka.get_template", return_value=mock_template),
        mock.patch("pivni_valka.Path") as mock_path,
        mock.patch("pivni_valka.pushover") as mock_pushover,
    ):
        mock_path.side_effect = lambda p: {"dist/pivni-valka/index.html": index_html}[p]
        pv._main()

    mock_pushover.send_notification.assert_not_called()

    assert index_html.read_text() == "rendered"


def test_main_with_notification(tmp_path):
    pv = PivniValka()
    pv._args = Args()

    output_dir = tmp_path / "pivni-valka"
    output_dir.mkdir()
    index_html = output_dir / "index.html"

    mock_template = jinja2.Template("rendered")

    with (
        mock.patch.object(pv, "get_unique_beers_count", return_value={"sejrik": 100}),
        mock.patch.object(pv, "save_daily_stats_db", return_value=["sejrik"]),
        mock.patch.object(pv, "get_yesterday_status", return_value="Status message"),
        mock.patch("pivni_valka.get_template", return_value=mock_template),
        mock.patch("pivni_valka.Path") as mock_path,
        mock.patch("pivni_valka.pushover") as mock_pushover,
    ):
        mock_path.side_effect = lambda p: {"dist/pivni-valka/index.html": index_html}[p]
        pv._main()

    mock_pushover.send_notification.assert_called_once_with("Status message", html=True)
