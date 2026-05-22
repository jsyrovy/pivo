import logging
from unittest import mock

import pytest

from notifier.base import Beer, Offer, get_cleaned_beer, is_in_archive


def test_is_in_archive():
    assert is_in_archive(Beer("Three Suns", "Sibeeria"))
    assert is_in_archive(Beer("Three Suns", "Pivovar Sibeeria"))
    assert is_in_archive(Beer("24° Three Suns", "Sibeeria"))
    assert is_in_archive(Beer("Three Suns 24°", "Sibeeria pivovar"))


def test_is_not_in_archive():
    assert not is_in_archive(Beer("Nonexistent Beer", "Unknown Brewery"))


def test_get_cleaned_beer():
    assert get_cleaned_beer(Beer("  Beer 10° ", " pivovar Brewery  ")) == Beer("beer", "brewery")


def test_get_cleaned_beer_no_degree_no_pivovar():
    assert get_cleaned_beer(Beer("Simple", "Brewery")) == Beer("simple", "brewery")


def test_beer():
    json_ = {"name": "Test Beer", "description": "Test Brewery"}
    beer = Beer.from_json(json_)

    assert beer.name == json_["name"]
    assert beer.description == json_["description"]
    assert beer.tasted is False
    assert beer.to_json() == json_
    assert str(beer) == f"{json_['name']} 🆕\n{json_['description']}"


def test_beer_str_tasted():
    beer = Beer("Tasted Beer", "Brewery", tasted=True)
    assert str(beer) == "Tasted Beer\nBrewery"


def test_offer_init():
    offer = Offer()
    assert offer._previous_beers == []
    assert offer._current_beers == []
    assert offer.new_beers == []


def test_offer_run_raises():
    offer = Offer()
    with pytest.raises(NotImplementedError):
        offer.run()


def test_offer_send_notification_notificationless(caplog):
    offer = Offer()
    offer.new_beers = [Beer("New IPA", "Cool Brewery")]

    with caplog.at_level(logging.INFO, logger="notifier.base"):
        offer.send_notification(notificationless=True)

    assert "Nově na čepu" in caplog.text
    assert "New IPA" in caplog.text
    assert "Cool Brewery" in caplog.text


def test_offer_send_notification_pushover():
    offer = Offer()
    offer.new_beers = [Beer("New IPA", "Cool Brewery")]

    with mock.patch("notifier.base.pushover.send_notification") as mock_send:
        offer.send_notification(notificationless=False)

    mock_send.assert_called_once()
    message = mock_send.call_args.args[0]
    assert mock_send.call_args.kwargs.get("html") is True
    assert "<b>Nově na čepu" in message
    assert "<b>New IPA</b>" in message
    assert "🆕" in message


def test_offer_send_notification_escapes_html_special_chars():
    offer = Offer()
    offer.new_beers = [Beer("Maisel & Friends Urban IPA", "Brauerei Gebr. Maisel")]

    with mock.patch("notifier.base.pushover.send_notification") as mock_send:
        offer.send_notification(notificationless=False)

    message = mock_send.call_args.args[0]
    assert "Maisel &amp; Friends" in message
    assert "Maisel & Friends" not in message


def test_offer_set_tasted():
    offer = Offer()
    offer.new_beers = [
        Beer("Three Suns", "Sibeeria"),
        Beer("Nonexistent Beer", "Unknown Brewery"),
    ]

    offer.set_tasted()

    assert offer.new_beers[0].tasted is True
    assert offer.new_beers[1].tasted is False
