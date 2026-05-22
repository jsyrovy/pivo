from __future__ import annotations

import datetime
import random
from html import escape as html_escape
from pathlib import Path
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

import utils.user
from pivni_valka.stats import common, tiles, weekly_chart
from pivni_valka.stats.common import ChartData
from pivni_valka.stats.tiles import TileData
from pivni_valka.stats.total_chart import get_all_chart_data, slice_chart_data
from robot.orm import OrmRobot
from utils import pushover
from utils.common import DASHBOARD_BASE_URL, download_page, get_profile_url, get_template, random_sleep

if TYPE_CHECKING:
    import jinja2

GetPageKwArgs = list[TileData] | ChartData | str

DASHBOARD_URL = f"{DASHBOARD_BASE_URL}/pivni-valka"


class PivniValka(OrmRobot):
    def _main(self) -> None:
        unique_beers_count = self.get_unique_beers_count()
        users_with_new_beers = self.save_daily_stats_db(unique_beers_count)

        all_chart_data = get_all_chart_data()

        page = self.get_page(
            get_template("pivni-valka.html"),
            active_page="pivni-valka",
            tiles_data=tiles.get_tiles_data(),
            total_chart_data_14=slice_chart_data(all_chart_data, days=14),
            total_chart_data_30=slice_chart_data(all_chart_data, days=30),
            total_chart_data_365=slice_chart_data(all_chart_data, days=365),
            total_chart_data_all=all_chart_data,
            weekly_chart_data=weekly_chart.get_chart_data(),
        )

        output = Path("dist/pivni-valka/index.html")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w") as f:
            f.write(page)

        if not self._args.local and not self._args.notificationless and users_with_new_beers:
            status = self.get_yesterday_status(users_with_new_beers)
            pushover.send_notification(status, html=True)

    def get_unique_beers_count(self) -> dict[str, int]:
        data: dict[str, int] = {}

        if self._args.publish:
            return data

        if self._args.local:
            total_unique_beers = common.get_total_unique_beers()
            for user_name in utils.user.USER_NAMES:
                data[user_name] = total_unique_beers[user_name] + random.randint(0, 10)
            return data

        for user_name in utils.user.USER_NAMES:
            user_profile = download_page(get_profile_url(user_name))
            data[user_name] = self.parse_unique_beers_count(user_profile)
            random_sleep()

        return data

    @staticmethod
    def parse_unique_beers_count(user_profile: str) -> int:
        soup = BeautifulSoup(user_profile, "html.parser")

        try:
            unique_beers_count = soup.find("div", class_="stats").find_all("a")[1].find("span", class_="stat").text  # type: ignore[union-attr]
        except Exception as e:
            raise ValueError("Cannot parse user profile.") from e

        return int(unique_beers_count.replace(",", ""))

    @staticmethod
    def get_page(template: jinja2.Template, **kwargs: GetPageKwArgs) -> str:
        return template.render(**kwargs)

    @staticmethod
    def save_daily_stats_db(unique_beers_count: dict[str, int]) -> list[str]:
        users_with_new_beers: list[str] = []

        if not unique_beers_count:
            return users_with_new_beers

        yesterday = datetime.date.today() - datetime.timedelta(days=1)

        for user_name in utils.user.USER_NAMES:
            new_beers = unique_beers_count[user_name] - common.get_unique_beers_before(user_name, before=yesterday)
            common.save_daily_stats(yesterday, user_name, new_beers)

            if new_beers:
                users_with_new_beers.append(user_name)

        return users_with_new_beers

    @staticmethod
    def get_yesterday_status(users_with_new_beers: list[str]) -> str:
        if not users_with_new_beers:
            return ""

        total_unique_beers = common.get_total_unique_beers()

        yesterday_lines = [
            f"<b>{html_escape(user.name)}</b> "
            f"vypil{'a' if user.sex == 'female' else ''} "
            f"<b>{common.get_unique_beers(user.user_name, days=1)}</b> 🍺"
            for user in utils.user.VISIBLE_USERS
            if user.user_name in users_with_new_beers
        ]
        total_lines = [
            f"<b>{html_escape(user.name)}</b>: <b>{total_unique_beers[user.user_name]}</b> 🍺"
            for user in utils.user.VISIBLE_USERS
        ]

        sections = [
            "<b>Včera:</b>\n" + "\n".join(yesterday_lines),
            "<b>Celkem:</b>\n" + "\n".join(total_lines),
            f'<a href="{DASHBOARD_URL}">Přehled</a>',
        ]
        return "\n\n".join(sections)

    @staticmethod
    def get_grid_template_areas() -> tuple[str, ...]:
        user_items = [f"item-{user_name}" for user_name in utils.user.VISIBLE_USER_NAMES]

        return (
            f'"{" ".join(user_items)}"',
            f'"{" ".join(["item-total-chart"] * len(user_items))}"',
            f'"{" ".join(["item-weekly-chart"] * len(user_items))}"',
        )

    @staticmethod
    def get_mobile_grid_template_areas() -> list[str]:
        user_items = [f'"item-{user_name}"' for user_name in utils.user.VISIBLE_USER_NAMES]
        user_items.extend(
            [
                '"item-total-chart"',
                '"item-weekly-chart"',
            ],
        )

        return user_items
