"""The booking conversation, as pure logic.

No database, no network, no model. Each step is a function from (booking,
event) to (new booking, messages to send). A whole reservation can therefore be
replayed in a test without a phone, a SIM card or a running server.

The host answers on a basic phone, so every question we ask is closed and every
answer we accept is one character. People still type "oui" or "Yes please", so
replies are normalised before they are read, and anything unreadable earns one
polite re-prompt rather than a silent failure.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from enum import Enum

from . import templates as tpl

# How long the visitor waits before we give up on the host.
HOST_REPLY_WINDOW = timedelta(hours=2)
# How early the host gets the arrival reminder.
REMINDER_LEAD = timedelta(days=1)
# After this many unreadable replies we stop re-prompting, to avoid an SMS loop.
MAX_BAD_REPLIES = 3


class State(str, Enum):
    AWAITING_HOST = "awaiting_host"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    ALT_DATE = "alt_date"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


TERMINAL = {State.DECLINED, State.ALT_DATE, State.EXPIRED, State.CANCELLED}

# What a host may actually type, mapped to the digit we asked for.
REPLY_ALIASES: dict[str, str] = {
    "1": "1", "oui": "1", "yes": "1", "ok": "1", "o": "1", "y": "1",
    "dakor": "1", "daccord": "1", "bien": "1",
    "2": "2", "non": "2", "no": "2", "n": "2",
    "3": "3", "autre": "3", "autredate": "3", "other": "3", "change": "3",
    "9": "9", "annuler": "9", "cancel": "9", "stop": "9",
}


def normalise_reply(raw: str) -> str | None:
    """Turn what the host typed into 1, 2, 3, 9, or None when unreadable.

    Hosts do not answer like a form. They send "1", " 1 ", "Oui merci",
    "d'accord" or nothing readable at all. So we strip accents, case and
    punctuation, then look for a known word or digit, first across the whole
    message and then token by token. A message carrying two different answers
    ("1 ou 2") is treated as unreadable rather than guessed at.
    """
    if raw is None:
        return None
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()

    squeezed = re.sub(r"[^a-z0-9]", "", text)
    if not squeezed:
        return None

    # Whole message first. This is what catches "1", "oui", "d'accord",
    # "autre date" and the one-letter answers like "o" or "n".
    if squeezed in REPLY_ALIASES:
        return REPLY_ALIASES[squeezed]

    found: set[str] = set()
    for token in (t for t in re.split(r"[^a-z0-9]+", text) if t):
        # A lone letter only counts when it is the entire message, otherwise
        # "on y va" would read as a yes.
        if len(token) == 1 and token.isalpha():
            continue
        if token in REPLY_ALIASES:
            found.add(REPLY_ALIASES[token])
        elif token in {"1", "2", "3", "9"}:
            found.add(token)

    return found.pop() if len(found) == 1 else None


@dataclass(frozen=True)
class Request:
    """What the visitor asked for, already structured."""

    visitor_id: str
    visitor_lang: str
    listing_id: str
    check_in: date
    nights: int
    guests: int
    breakfast: bool = False

    @property
    def check_out(self) -> date:
        return self.check_in + timedelta(days=self.nights)


@dataclass(frozen=True)
class Outbound:
    """One message Karibu wants to send."""

    to: str
    channel: str  # "sms" to a phone, "web" to the visitor page
    lang: str
    key: str
    params: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return tpl.render(self.key, self.lang, self.params)


@dataclass
class Booking:
    ref: str
    request: Request
    host_phone: str
    price_total: int
    currency: str = "FCFA"
    host_lang: str = "fr"
    visitor_name: str = ""
    state: State = State.AWAITING_HOST
    created_at: datetime = field(default_factory=datetime.now)
    settled_at: datetime | None = None
    bad_replies: int = 0
    reminder_sent: bool = False

    @property
    def is_open(self) -> bool:
        return self.state == State.AWAITING_HOST


def _host_params(booking: Booking) -> dict:
    req = booking.request
    return {
        "ref": booking.ref,
        "nights": req.nights,
        "stay": tpl.format_stay(req.check_in, req.nights),
        "arrival": tpl.format_day(req.check_in),
        "guests": req.guests,
        "meal": " +petit dej" if req.breakfast else "",
        "total": tpl.format_money(booking.price_total),
        "cur": booking.currency,
        "visitor": booking.visitor_name or "visiteur",
        "hours": int(HOST_REPLY_WINDOW.total_seconds() // 3600),
    }


def _visitor_params(booking: Booking) -> dict:
    req = booking.request
    return {
        "ref": booking.ref,
        "stay": tpl.format_stay(req.check_in, req.nights),
        "guests": req.guests,
        "meal": " + breakfast" if req.breakfast else "",
        "total": tpl.format_money(booking.price_total),
        "cur": booking.currency,
        "hours": int(HOST_REPLY_WINDOW.total_seconds() // 3600),
    }


def _to_host(booking: Booking, key: str) -> Outbound:
    return Outbound(booking.host_phone, "sms", booking.host_lang, key, _host_params(booking))


def _to_visitor(booking: Booking, key: str) -> Outbound:
    return Outbound(
        booking.request.visitor_id, "web", booking.request.visitor_lang, key,
        _visitor_params(booking),
    )


def open_booking(
    ref: str,
    request: Request,
    host_phone: str,
    price_total: int,
    currency: str = "FCFA",
    visitor_name: str = "",
    now: datetime | None = None,
) -> tuple[Booking, list[Outbound]]:
    """Start a booking: one SMS to the host, one acknowledgement to the visitor."""
    booking = Booking(
        ref=ref,
        request=request,
        host_phone=host_phone,
        price_total=price_total,
        currency=currency,
        visitor_name=visitor_name,
        created_at=now or datetime.now(),
    )
    return booking, [_to_host(booking, "host_request"), _to_visitor(booking, "visitor_pending")]


def on_host_reply(
    booking: Booking, raw: str, now: datetime | None = None
) -> tuple[Booking, list[Outbound]]:
    """Read what the host texted back and move the booking along."""
    now = now or datetime.now()
    digit = normalise_reply(raw)

    # A confirmed booking can still be cancelled by the host.
    if booking.state == State.CONFIRMED:
        if digit == "9":
            updated = replace(booking, state=State.CANCELLED, settled_at=now)
            return updated, [
                _to_host(updated, "host_cancel_ack"),
                _to_visitor(updated, "visitor_cancelled"),
            ]
        return booking, []

    if booking.state in TERMINAL:
        return booking, []

    if digit == "1":
        updated = replace(booking, state=State.CONFIRMED, settled_at=now, bad_replies=0)
        return updated, [
            _to_host(updated, "host_confirmed_ack"),
            _to_visitor(updated, "visitor_confirmed"),
        ]
    if digit == "2":
        updated = replace(booking, state=State.DECLINED, settled_at=now, bad_replies=0)
        return updated, [
            _to_host(updated, "host_declined_ack"),
            _to_visitor(updated, "visitor_declined"),
        ]
    if digit == "3":
        updated = replace(booking, state=State.ALT_DATE, settled_at=now, bad_replies=0)
        return updated, [
            _to_host(updated, "host_alt_ack"),
            _to_visitor(updated, "visitor_alt_date"),
        ]
    if digit == "9":
        # Nothing to cancel yet: treat it as a refusal.
        updated = replace(booking, state=State.DECLINED, settled_at=now, bad_replies=0)
        return updated, [
            _to_host(updated, "host_declined_ack"),
            _to_visitor(updated, "visitor_declined"),
        ]

    # Unreadable. Ask once more, but never loop forever.
    updated = replace(booking, bad_replies=booking.bad_replies + 1)
    if updated.bad_replies > MAX_BAD_REPLIES:
        return updated, []
    return updated, [_to_host(updated, "host_reprompt")]


def on_tick(booking: Booking, now: datetime | None = None) -> tuple[Booking, list[Outbound]]:
    """Time-driven steps: the two-hour timeout and the day-before reminder."""
    now = now or datetime.now()

    if booking.state == State.AWAITING_HOST:
        if now - booking.created_at >= HOST_REPLY_WINDOW:
            updated = replace(booking, state=State.EXPIRED, settled_at=now)
            return updated, [
                _to_host(updated, "host_expired"),
                _to_visitor(updated, "visitor_expired"),
            ]
        return booking, []

    if booking.state == State.CONFIRMED and not booking.reminder_sent:
        arrival = datetime.combine(booking.request.check_in, datetime.min.time())
        if now >= arrival - REMINDER_LEAD:
            updated = replace(booking, reminder_sent=True)
            return updated, [_to_host(updated, "host_reminder")]

    return booking, []
