"""Extraction, with and without the model.

The rule is simple and the tests hold it: the model may fill a blank, never
correct a rule.
"""

from datetime import date

from hub.services.extract import Extraction, extract
from hub.services.ollama import ModelUnavailable

TODAY = date(2026, 10, 8)


class FakeModel:
    """Stands in for the local model runner."""

    def __init__(self, payload=None, fail=False):
        self.payload = payload or {}
        self.fail = fail
        self.calls = 0

    def generate_json(self, prompt):
        self.calls += 1
        if self.fail:
            raise ModelUnavailable("runner is down")
        return self.payload


def test_rules_alone_read_a_complete_message():
    got = extract("10월 12일부터 2박, 2명", today=TODAY, model=None)
    assert got.check_in == date(2026, 10, 12)
    assert got.nights == 2 and got.guests == 2
    assert got.complete and not got.needs_host_care


def test_the_model_is_not_called_when_the_rules_are_enough():
    model = FakeModel({"check_in": "2030-01-01", "nights": 99, "guests": 99})
    got = extract("12-14 October, 2 people", today=TODAY, model=model)
    assert model.calls == 0
    assert got.check_in == date(2026, 10, 12) and got.guests == 2


def test_the_model_may_not_overwrite_a_rule():
    model = FakeModel({"check_in": "2026-11-30", "nights": 9, "guests": 9})
    got = extract("next friday, 3 nights, 2 people", today=TODAY, model=model)
    assert got.nights == 3, "the rule read 3 nights and must win"
    assert got.guests == 2
    assert got.check_in == date(2026, 11, 30), "the blank was filled by the model"
    assert got.read_by["check_in"] == "model"
    assert got.read_by["nights"] == "rule"
    assert got.needs_host_care


def test_a_date_in_the_past_from_the_model_is_dropped():
    model = FakeModel({"check_in": "2019-04-01"})
    got = extract("next week please", today=TODAY, model=model)
    assert got.check_in is None


def test_an_absurd_head_count_from_the_model_is_dropped():
    model = FakeModel({"guests": 400})
    got = extract("a room next week", today=TODAY, model=model)
    assert got.read_by.get("guests") != "model"


def test_a_dead_model_does_not_break_the_request():
    model = FakeModel(fail=True)
    got = extract("a room on 12 October", today=TODAY, model=model)
    assert got.check_in == date(2026, 10, 12)
    assert got.nights == 1 and got.guests == 2
    assert got.read_by["nights"] == "default"


def test_defaults_fill_the_rest_so_the_host_still_gets_a_question():
    got = extract("bonjour", today=TODAY, model=None)
    assert got.nights == 1 and got.guests == 2 and got.breakfast is False
    assert got.check_in is None
    assert not got.complete
