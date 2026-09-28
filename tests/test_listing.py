"""What a host says on the phone, and what Karibu makes of it."""

import pytest

from hub.services.listing import read

SPOKEN = ("J'ai deux chambres, huit mille francs la nuit avec le petit dejeuner, "
          "c'est a Bafang pres des chutes.")


def test_the_demo_recording():
    got = read(SPOKEN)
    assert got.rooms == 2
    assert got.price_per_night == 8000
    assert got.breakfast is True
    assert got.place and "Bafang" in got.place
    assert got.complete
    assert got.read_by["price_per_night"] == "rule"


def test_digits_work_as_well_as_words():
    got = read("J'ai 3 chambres a 12 000 francs la nuit, sans petit dejeuner.")
    assert got.rooms == 3
    assert got.price_per_night == 12000
    assert got.breakfast is False


def test_price_given_per_night_without_the_word_franc():
    got = read("une chambre, quinze mille la nuit")
    assert got.rooms == 1
    assert got.price_per_night == 15000


def test_a_number_with_no_unit_is_not_taken_for_a_price():
    got = read("bonjour, j'ai deux chambres")
    assert got.rooms == 2
    assert got.price_per_night is None
    assert not got.complete


def test_an_empty_recording_reads_nothing():
    got = read("euh... allo ?")
    assert got.rooms is None and got.price_per_night is None
    assert not got.complete
