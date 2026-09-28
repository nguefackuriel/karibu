"""What the rules must read without ever asking the model.

The cases below are the ones a 1B model got wrong in testing, plus the three
languages the demo uses. Anything here that regressed would put a host on the
wrong doorstep.
"""

from datetime import date

import pytest

from hub.services import dates

TODAY = date(2026, 10, 8)


def read(message):
    return dates.read(message, TODAY)


# --- the case the model failed -----------------------------------------------


def test_french_range_keeps_the_first_date():
    got = read("Bonjour, avez-vous de la place pour 3 personnes du 20 au 23 octobre ?")
    assert got.check_in == date(2026, 10, 20)
    assert got.nights == 3
    assert got.guests == 3
    assert got.read_by["check_in"] == "rule"


def test_english_range():
    got = read("Room from 20th to 23rd October for 2 guests please")
    assert got.check_in == date(2026, 10, 20)
    assert got.nights == 3
    assert got.guests == 2


def test_dash_range():
    got = read("12-14 October, 2 people")
    assert got.check_in == date(2026, 10, 12)
    assert got.nights == 2


# --- Korean, the demo language ------------------------------------------------


def test_korean_date_nights_and_guests():
    got = read("10월 12일부터 2박, 2명 가능한가요? 아침 식사 포함인가요?")
    assert got.check_in == date(2026, 10, 12)
    assert got.nights == 2
    assert got.guests == 2
    assert got.breakfast is True


def test_korean_alone_means_one_guest():
    got = read("혼자입니다. 3박 하고 싶어요.")
    assert got.guests == 1
    assert got.nights == 3


def test_korean_person_counter_in():
    got = read("10월 3일, 4인")
    assert got.check_in == date(2026, 10, 3) or got.check_in == date(2027, 10, 3)
    assert got.guests == 4


# --- English and French singles -----------------------------------------------


def test_english_month_first():
    got = read("Do you have a room on October 12th for two nights?")
    assert got.check_in == date(2026, 10, 12)


def test_french_single_date_with_nights():
    got = read("12 octobre, 2 nuits, 2 personnes, avec petit dejeuner")
    assert got.check_in == date(2026, 10, 12)
    assert got.nights == 2
    assert got.guests == 2
    assert got.breakfast is True


def test_numeric_date():
    got = read("20/10, 2 nuits")
    assert got.check_in == date(2026, 10, 20)


# --- breakfast, including the refusals ----------------------------------------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("avec petit dejeuner", True),
        ("sans petit dejeuner", False),
        ("breakfast included?", True),
        ("no breakfast please", False),
        ("without breakfast", False),
        ("une chambre simple", None),
    ],
)
def test_breakfast(message, expected):
    assert read(message).breakfast is expected


# --- the year, and what the rules refuse to guess ------------------------------


def test_a_past_month_means_next_year():
    got = dates.read("3 janvier, 2 nuits", date(2026, 10, 8))
    assert got.check_in == date(2027, 1, 3)


def test_relative_dates_are_left_to_the_model():
    got = read("next week friday for 3 nights")
    assert got.check_in is None, "rules must not guess relative dates"
    assert got.nights == 3


def test_an_empty_message_reads_nothing():
    got = read("bonjour")
    assert got.check_in is None and got.nights is None and got.guests is None
