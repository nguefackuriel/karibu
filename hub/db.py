"""Storage for the hub: one SQLite file, no server, no migrations.

A tourism office with intermittent power and no IT staff should be able to copy
the whole system onto a USB key. That rules out a database server, so every
table lives in one file next to the code.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "karibu.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS hosts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL UNIQUE,
    lang        TEXT NOT NULL DEFAULT 'fr',
    village     TEXT,
    site        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,
    host_id         TEXT NOT NULL REFERENCES hosts(id),
    rooms           INTEGER NOT NULL,
    price_per_night INTEGER NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'FCFA',
    breakfast       INTEGER NOT NULL DEFAULT 0,
    place           TEXT,
    description     TEXT,
    created_by      TEXT NOT NULL DEFAULT 'voice',
    confirmed       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    ref           TEXT PRIMARY KEY,
    listing_id    TEXT NOT NULL REFERENCES listings(id),
    visitor_id    TEXT NOT NULL,
    visitor_lang  TEXT NOT NULL DEFAULT 'en',
    visitor_name  TEXT,
    check_in      TEXT NOT NULL,
    nights        INTEGER NOT NULL,
    guests        INTEGER NOT NULL,
    breakfast     INTEGER NOT NULL DEFAULT 0,
    price_total   INTEGER NOT NULL,
    currency      TEXT NOT NULL DEFAULT 'FCFA',
    state         TEXT NOT NULL,
    read_by       TEXT,
    created_at    TEXT NOT NULL,
    settled_at    TEXT,
    bad_replies   INTEGER NOT NULL DEFAULT 0,
    reminder_sent INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_ref TEXT,
    direction   TEXT NOT NULL,
    channel     TEXT NOT NULL,
    peer        TEXT NOT NULL,
    lang        TEXT,
    template    TEXT,
    body        TEXT NOT NULL,
    segments    INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bookings_state   ON bookings(state);
CREATE INDEX IF NOT EXISTS idx_bookings_listing ON bookings(listing_id);
CREATE INDEX IF NOT EXISTS idx_messages_booking ON messages(booking_ref);
CREATE INDEX IF NOT EXISTS idx_listings_host    ON listings(host_id);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(path) if path else DEFAULT_PATH
    connection = sqlite3.connect(target, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- hosts and listings -------------------------------------------------------


def add_host(db, host_id, name, phone, village=None, site=None, lang="fr"):
    db.execute(
        "INSERT OR REPLACE INTO hosts (id, name, phone, lang, village, site, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (host_id, name, phone, lang, village, site, now_iso()),
    )
    db.commit()


def add_listing(db, listing_id, host_id, rooms, price_per_night, place=None,
                breakfast=False, description=None, currency="FCFA",
                created_by="voice", confirmed=False):
    db.execute(
        "INSERT OR REPLACE INTO listings (id, host_id, rooms, price_per_night, currency,"
        " breakfast, place, description, created_by, confirmed, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (listing_id, host_id, rooms, price_per_night, currency, int(breakfast), place,
         description, created_by, int(confirmed), now_iso()),
    )
    db.commit()


def get_listing(db, listing_id):
    return db.execute(
        "SELECT l.*, h.name AS host_name, h.phone AS host_phone, h.lang AS host_lang,"
        " h.village AS host_village, h.site AS host_site"
        " FROM listings l JOIN hosts h ON h.id = l.host_id WHERE l.id = ?",
        (listing_id,),
    ).fetchone()


def all_listings(db):
    return db.execute(
        "SELECT l.*, h.name AS host_name, h.village AS host_village, h.site AS host_site"
        " FROM listings l JOIN hosts h ON h.id = l.host_id"
        " WHERE l.confirmed = 1 ORDER BY l.created_at"
    ).fetchall()


def confirm_listing(db, listing_id, confirmed=True):
    db.execute("UPDATE listings SET confirmed = ? WHERE id = ?", (int(confirmed), listing_id))
    db.commit()


def host_by_phone(db, phone):
    return db.execute("SELECT * FROM hosts WHERE phone = ?", (phone,)).fetchone()


# --- bookings -----------------------------------------------------------------


def save_booking(db, booking, read_by: str | None = None):
    request = booking.request
    db.execute(
        "INSERT OR REPLACE INTO bookings (ref, listing_id, visitor_id, visitor_lang,"
        " visitor_name, check_in, nights, guests, breakfast, price_total, currency,"
        " state, read_by, created_at, settled_at, bad_replies, reminder_sent)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            booking.ref, request.listing_id, request.visitor_id, request.visitor_lang,
            booking.visitor_name, request.check_in.isoformat(), request.nights,
            request.guests, int(request.breakfast), booking.price_total, booking.currency,
            booking.state.value, read_by, booking.created_at.isoformat(timespec="seconds"),
            booking.settled_at.isoformat(timespec="seconds") if booking.settled_at else None,
            booking.bad_replies, int(booking.reminder_sent),
        ),
    )
    db.commit()


def get_booking_row(db, ref):
    return db.execute("SELECT * FROM bookings WHERE ref = ?", (ref,)).fetchone()


def open_booking_for_phone(db, phone):
    """The booking a host's SMS is about: their most recent unsettled one."""
    return db.execute(
        "SELECT b.* FROM bookings b"
        " JOIN listings l ON l.id = b.listing_id"
        " JOIN hosts h ON h.id = l.host_id"
        " WHERE h.phone = ? AND b.state IN ('awaiting_host','confirmed')"
        " ORDER BY b.created_at DESC LIMIT 1",
        (phone,),
    ).fetchone()


def bookings_awaiting(db):
    return db.execute(
        "SELECT * FROM bookings WHERE state IN ('awaiting_host','confirmed')"
    ).fetchall()


def all_bookings(db):
    return db.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall()


# --- messages -----------------------------------------------------------------


def log_message(db, booking_ref, direction, channel, peer, body,
                lang=None, template=None, segments=1):
    db.execute(
        "INSERT INTO messages (booking_ref, direction, channel, peer, lang, template,"
        " body, segments, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (booking_ref, direction, channel, peer, lang, template, body, segments, now_iso()),
    )
    db.commit()


def messages_for(db, booking_ref):
    return db.execute(
        "SELECT * FROM messages WHERE booking_ref = ? ORDER BY id", (booking_ref,)
    ).fetchall()


def recent_messages(db, limit=50):
    return db.execute(
        "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
