"""The booking conversation, replayed without a phone.

These tests are the demo written down: a Korean visitor asks, the host answers
from a basic phone, everyone gets the right message. They also guard the two
promises Karibu makes to a feature phone, namely that every host message is one
SMS segment and that a human answer like "oui" is understood.
"""

from datetime import date, datetime, timedelta

import pytest

from hub import templates as tpl
from hub.booking import (
    HOST_REPLY_WINDOW,
    MAX_BAD_REPLIES,
    Booking,
    Request,
    State,
    normalise_reply,
    on_host_reply,
    on_tick,
    open_booking,
)

HOST = "+237600000001"
NOW = datetime(2026, 10, 10, 9, 0)


def make_request(**kwargs) -> Request:
    base = dict(
        visitor_id="v-001",
        visitor_lang="ko",
        listing_id="L1",
        check_in=date(2026, 10, 12),
        nights=2,
        guests=2,
        breakfast=True,
    )
    base.update(kwargs)
    return Request(**base)


def start(**kwargs):
    return open_booking(
        ref="K7F3",
        request=make_request(**kwargs),
        host_phone=HOST,
        price_total=16000,
        visitor_name="Mme Kim",
        now=NOW,
    )


# --- the happy path, which is the demo ---------------------------------------


def test_request_sends_one_sms_to_host_and_an_ack_to_the_visitor():
    booking, out = start()
    assert booking.state == State.AWAITING_HOST
    assert len(out) == 2

    to_host, to_visitor = out
    assert to_host.channel == "sms"
    assert to_host.to == HOST
    assert "1=OUI" in to_host.text
    assert "12-14 oct" in to_host.text

    assert to_visitor.channel == "web"
    assert to_visitor.lang == "ko"


def test_host_replies_one_and_everyone_is_told():
    booking, _ = start()
    booking, out = on_host_reply(booking, "1", now=NOW + timedelta(minutes=4))

    assert booking.state == State.CONFIRMED
    assert booking.settled_at is not None
    keys = [message.key for message in out]
    assert keys == ["host_confirmed_ack", "visitor_confirmed"]
    assert "K7F3" in out[1].text


def test_confirmation_reaches_the_visitor_in_korean():
    booking, _ = start(visitor_lang="ko")
    _, out = on_host_reply(booking, "1")
    visitor_message = out[1]
    assert visitor_message.lang == "ko"
    # Korean text, not an English fallback.
    assert any("가" <= ch <= "힣" for ch in visitor_message.text)


# --- the answers a real host actually sends ----------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1", "1"), (" 1 ", "1"), ("oui", "1"), ("OUI", "1"), ("Oui.", "1"),
        ("yes", "1"), ("ok", "1"), ("d'accord", "1"), ("1 merci", "1"),
        ("2", "2"), ("non", "2"), ("NON", "2"), ("no", "2"),
        ("3", "3"), ("autre", "3"), ("autre date", "3"),
        ("9", "9"), ("annuler", "9"), ("cancel", "9"),
        ("", None), ("   ", None), ("peut etre", None), ("1 ou 2", None),
        ("bonjour comment ca va", None), (None, None),
        ("on y va", None), ("y", "1"), ("o", "1"), ("12", None), ("???", None),
    ],
)
def test_normalise_reply(raw, expected):
    assert normalise_reply(raw) == expected


def test_a_written_oui_confirms_just_like_the_digit():
    booking, _ = start()
    booking, out = on_host_reply(booking, "Oui merci")
    assert booking.state == State.CONFIRMED
    assert out[0].key == "host_confirmed_ack"


def test_unreadable_reply_earns_one_reprompt_and_keeps_the_booking_open():
    booking, _ = start()
    booking, out = on_host_reply(booking, "peut etre demain")
    assert booking.state == State.AWAITING_HOST
    assert booking.bad_replies == 1
    assert out[0].key == "host_reprompt"


def test_karibu_stops_reprompting_instead_of_looping():
    booking, _ = start()
    for _ in range(MAX_BAD_REPLIES):
        booking, out = on_host_reply(booking, "???")
        assert out, "should still be re-prompting"
    booking, out = on_host_reply(booking, "???")
    assert out == [], "no SMS loop with a confused host"
    assert booking.state == State.AWAITING_HOST


# --- refusal, other dates, cancellation --------------------------------------


def test_host_refuses():
    booking, _ = start()
    booking, out = on_host_reply(booking, "2")
    assert booking.state == State.DECLINED
    assert [m.key for m in out] == ["host_declined_ack", "visitor_declined"]


def test_host_asks_for_other_dates():
    booking, _ = start()
    booking, out = on_host_reply(booking, "3")
    assert booking.state == State.ALT_DATE
    assert [m.key for m in out] == ["host_alt_ack", "visitor_alt_date"]


def test_host_cancels_after_confirming():
    booking, _ = start()
    booking, _ = on_host_reply(booking, "1")
    booking, out = on_host_reply(booking, "9", now=NOW + timedelta(days=1))
    assert booking.state == State.CANCELLED
    assert [m.key for m in out] == ["host_cancel_ack", "visitor_cancelled"]


def test_a_settled_booking_ignores_further_replies():
    booking, _ = start()
    booking, _ = on_host_reply(booking, "2")
    booking, out = on_host_reply(booking, "1")
    assert booking.state == State.DECLINED
    assert out == []


# --- time ---------------------------------------------------------------------


def test_nothing_happens_before_the_window_closes():
    booking, _ = start()
    booking, out = on_tick(booking, now=NOW + HOST_REPLY_WINDOW - timedelta(minutes=1))
    assert booking.state == State.AWAITING_HOST
    assert out == []


def test_silence_expires_the_request_and_frees_the_visitor():
    booking, _ = start()
    booking, out = on_tick(booking, now=NOW + HOST_REPLY_WINDOW)
    assert booking.state == State.EXPIRED
    assert [m.key for m in out] == ["host_expired", "visitor_expired"]


def test_host_is_reminded_the_day_before_arrival():
    booking, _ = start()
    booking, _ = on_host_reply(booking, "1")
    booking, out = on_tick(booking, now=datetime(2026, 10, 11, 8, 0))
    assert booking.reminder_sent
    assert out[0].key == "host_reminder"
    assert "Repondre 9" in out[0].text


def test_the_reminder_is_sent_once():
    booking, _ = start()
    booking, _ = on_host_reply(booking, "1")
    booking, _ = on_tick(booking, now=datetime(2026, 10, 11, 8, 0))
    booking, out = on_tick(booking, now=datetime(2026, 10, 11, 20, 0))
    assert out == []


# --- the promise to the feature phone -----------------------------------------

HOST_KEYS = [key for key, variants in tpl.TEMPLATES.items() if key.startswith("host_")]


@pytest.mark.parametrize("key", HOST_KEYS)
def test_every_host_message_costs_exactly_one_sms(key):
    """160 GSM-7 characters. Two segments means double the cost for the host."""
    params = {
        "ref": "K7F3", "nights": 2, "stay": "12-14 oct", "arrival": "12 oct",
        "guests": 2, "meal": " +petit dej", "total": "16000", "cur": "FCFA",
        "visitor": "Mme Kim", "hours": 2, "rooms": 2, "price": "8000",
        "place": "Bafang, pres des chutes",
    }
    text = tpl.render(key, "fr", params)
    assert tpl.is_gsm7(text), f"{key} uses characters a basic phone cannot show cheaply"
    assert len(text) <= tpl.SMS_SEGMENT, f"{key} is {len(text)} characters, over one segment"


def test_date_range_stays_short_across_a_month_boundary():
    assert tpl.format_stay(date(2026, 9, 30), 2) == "30 sept-2 oct"
    assert tpl.format_stay(date(2026, 10, 12), 2) == "12-14 oct"


# --- the visitor reads their own language, not a mix --------------------------


def test_the_korean_confirmation_carries_no_french_month():
    booking, _ = start(visitor_lang="ko")
    _, out = on_host_reply(booking, "1")
    text = out[1].text
    assert "oct" not in text.lower(), "a Korean message must not carry a French month"
    assert "breakfast" not in text.lower(), "nor an English word for the meal"
    assert "10월 12일-14일" in text


def test_the_english_confirmation_uses_english_months():
    booking, _ = start(visitor_lang="en")
    _, out = on_host_reply(booking, "1")
    assert "12-14 Oct" in out[1].text


def test_the_host_sms_stays_french_whatever_the_visitor_speaks():
    booking, _ = start(visitor_lang="ko")
    _, out = on_host_reply(booking, "1")
    assert "12-14 oct" in out[0].text
