"""The Karibu hub: one small server that runs the whole thing.

Everything here runs on the machine the hub is installed on. In the demo that
is a laptop; in a tourism office it is a Raspberry Pi. Nothing in the booking
path calls out to the internet, which is what lets it keep working when the
connection does not.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from channels.gateway import Gateway, from_environment
from hub import booking as flow
from hub import db as store
from hub import templates as tpl
from hub.services.extract import extract
from hub.services.listing import read as read_listing
from hub.services.ollama import Ollama
from hub.services.voice import TranscriptionUnavailable, Whisper

STATIC_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "static"

state: dict = {}


def new_ref() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes on a small screen
    return "".join(secrets.choice(alphabet) for _ in range(4))


def load_env_file(path: Path | None = None) -> None:
    """Read .env if it is there, without overriding anything already set.

    Keeps the API key out of the shell history and out of the repository.
    """
    target = path or Path(__file__).resolve().parent.parent / ".env"
    if not target.exists():
        return
    for line in target.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_env_file()
    state["db"] = store.connect(os.environ.get("KARIBU_DB"))
    state["gateway"] = from_environment()
    state["model"] = Ollama(model=os.environ.get("KARIBU_MODEL", "gemma3:1b"))
    state["voice"] = Whisper(size=os.environ.get("KARIBU_WHISPER", "small"))
    yield
    state["db"].close()


app = FastAPI(title="Karibu hub", version="0.1.0", lifespan=lifespan)


# --- helpers ------------------------------------------------------------------


def row_to_booking(row, listing) -> flow.Booking:
    request = flow.Request(
        visitor_id=row["visitor_id"],
        visitor_lang=row["visitor_lang"],
        listing_id=row["listing_id"],
        check_in=date.fromisoformat(row["check_in"]),
        nights=row["nights"],
        guests=row["guests"],
        breakfast=bool(row["breakfast"]),
    )
    return flow.Booking(
        ref=row["ref"],
        request=request,
        host_phone=listing["host_phone"],
        price_total=row["price_total"],
        currency=row["currency"],
        host_lang=listing["host_lang"] or "fr",
        visitor_name=row["visitor_name"] or "",
        state=flow.State(row["state"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        settled_at=datetime.fromisoformat(row["settled_at"]) if row["settled_at"] else None,
        bad_replies=row["bad_replies"],
        reminder_sent=bool(row["reminder_sent"]),
    )


def deliver(messages: list[flow.Outbound], ref: str) -> list[dict]:
    """Send what the flow produced and write it all down."""
    db, gateway = state["db"], state["gateway"]
    delivered = []
    for message in messages:
        text = message.text
        status: dict = {}
        if message.channel == "sms":
            sent = gateway.send_sms(message.to, text)
            segments = sent.segments
            # Say whether the operator took it, so a failed send is visible
            # in the demo rather than discovered afterwards.
            status = {"accepted": sent.ok, "via": gateway.name}
            if not sent.ok:
                status["detail"] = sent.detail
        else:
            segments = 1
        store.log_message(db, ref, "out", message.channel, message.to, text,
                          lang=message.lang, template=message.key, segments=segments)
        delivered.append({
            "channel": message.channel, "to": message.to, "lang": message.lang,
            "template": message.key, "text": text, "segments": segments, **status,
        })
    return delivered


def load(ref: str):
    db = state["db"]
    row = store.get_booking_row(db, ref)
    if row is None:
        raise HTTPException(404, f"no booking {ref}")
    listing = store.get_listing(db, row["listing_id"])
    return row, listing, row_to_booking(row, listing)


# --- health and catalogue -----------------------------------------------------


@app.get("/health")
def health():
    model = state["model"]
    return {
        "status": "ok",
        "gateway": state["gateway"].name,
        "model": model.model,
        "model_reachable": model.available(),
        "voice": state["voice"].size,
        "voice_available": state["voice"].available(),
        "sms_configured": bool(os.environ.get("AT_API_KEY")),
    }


@app.get("/api/catalogue.json")
def catalogue():
    """The open catalogue any tourism portal can read.

    Shape follows the Beckn idea of a provider with items, so a destination
    portal can list these rooms without Karibu knowing anything about it.
    """
    db = state["db"]
    providers = []
    for row in store.all_listings(db):
        providers.append({
            "id": row["host_id"],
            "descriptor": {"name": row["host_name"]},
            "locations": [{"village": row["host_village"], "site": row["host_site"]}],
            "items": [{
                "id": row["id"],
                "descriptor": {"name": row["description"] or f"{row['rooms']} room(s)"},
                "quantity": {"available": {"count": row["rooms"]}},
                "price": {"currency": row["currency"], "value": row["price_per_night"],
                          "unit": "night"},
                "tags": {"breakfast": bool(row["breakfast"]), "place": row["place"]},
                "fulfillment": {"channel": "sms", "confirmation": "host_reply"},
            }],
        })
    return {"context": {"domain": "tourism", "version": "0.1"}, "providers": providers}


# --- the visitor --------------------------------------------------------------


@app.post("/api/requests")
async def create_request(payload: dict):
    db = state["db"]
    listing_id = payload.get("listing_id")
    message = (payload.get("message") or "").strip()
    lang = payload.get("lang") or "en"
    visitor_name = payload.get("visitor_name") or ""

    if not message:
        raise HTTPException(400, "message is empty")
    listing = store.get_listing(db, listing_id)
    if listing is None:
        raise HTTPException(404, f"no listing {listing_id}")

    reading = extract(message, today=date.today(), model=state["model"])
    if reading.check_in is None:
        return JSONResponse(
            {"understood": reading.as_dict(),
             "error": "no arrival date could be read from the message"},
            status_code=422,
        )

    price_total = listing["price_per_night"] * reading.nights
    request = flow.Request(
        visitor_id=payload.get("visitor_id") or f"v-{secrets.token_hex(3)}",
        visitor_lang=lang,
        listing_id=listing_id,
        check_in=reading.check_in,
        nights=reading.nights,
        guests=reading.guests,
        breakfast=bool(reading.breakfast),
    )
    ref = new_ref()
    created, messages = flow.open_booking(
        ref=ref, request=request, host_phone=listing["host_phone"],
        price_total=price_total, currency=listing["currency"], visitor_name=visitor_name,
    )
    created.host_lang = listing["host_lang"] or "fr"
    store.save_booking(db, created, read_by=str(reading.read_by))
    store.log_message(db, ref, "in", "web", request.visitor_id, message, lang=lang)
    delivered = deliver(messages, ref)

    return {"ref": ref, "state": created.state.value,
            "understood": reading.as_dict(), "sent": delivered}


@app.get("/api/requests/{ref}")
def request_status(ref: str):
    row, listing, current = load(ref)
    messages = [dict(m) for m in store.messages_for(state["db"], ref)]
    return {
        "ref": ref,
        "state": row["state"],
        "check_in": row["check_in"],
        "nights": row["nights"],
        "guests": row["guests"],
        "breakfast": bool(row["breakfast"]),
        "price_total": row["price_total"],
        "currency": row["currency"],
        "host_name": listing["host_name"],
        "place": listing["place"],
        "messages": messages,
    }


# --- the host -----------------------------------------------------------------


def pending_listing_for(phone: str):
    """A listing the host described but has not confirmed yet."""
    return state["db"].execute(
        "SELECT l.* FROM listings l JOIN hosts h ON h.id = l.host_id"
        " WHERE h.phone = ? AND l.confirmed = 0 ORDER BY l.created_at DESC LIMIT 1",
        (phone,),
    ).fetchone()


def handle_host_sms(sender: str, text: str) -> dict:
    db = state["db"]
    row = store.open_booking_for_phone(db, sender)

    if row is None:
        # No booking waiting, so this may be the answer to a new listing.
        listing = pending_listing_for(sender)
        if listing is not None:
            digit = flow.normalise_reply(text)
            store.log_message(db, listing["id"], "in", "sms", sender, text)
            if digit == "1":
                store.confirm_listing(db, listing["id"], True)
                return {"handled": True, "listing_id": listing["id"],
                        "state": "listing_confirmed", "understood": digit, "sent": []}
            if digit == "2":
                return {"handled": True, "listing_id": listing["id"],
                        "state": "listing_needs_correction", "understood": digit,
                        "sent": []}
        return {"handled": False, "reason": f"no open booking for {sender}"}

    listing = store.get_listing(db, row["listing_id"])
    current = row_to_booking(row, listing)
    store.log_message(db, current.ref, "in", "sms", sender, text)

    updated, messages = flow.on_host_reply(current, text)
    store.save_booking(db, updated, read_by=row["read_by"])
    return {
        "handled": True, "ref": updated.ref, "state": updated.state.value,
        "understood": flow.normalise_reply(text), "sent": deliver(messages, updated.ref),
    }


@app.post("/api/sms/inbound")
async def sms_inbound(request: Request):
    """Africa's Talking posts a form here when a host texts back."""
    form = await request.form()
    sender = (form.get("from") or "").strip()
    text = (form.get("text") or "").strip()
    if not sender:
        raise HTTPException(400, "missing sender")
    return handle_host_sms(sender, text)


@app.post("/api/sms/simulate")
async def sms_simulate(payload: dict):
    """The same thing without an account, so the demo runs anywhere."""
    return handle_host_sms((payload.get("from") or "").strip(),
                           (payload.get("text") or "").strip())


# --- the host signs up by voice -----------------------------------------------


def create_listing_from_transcript(transcript: str, phone: str, host_name: str = "") -> dict:
    """Turn a spoken description into a listing the host must still confirm."""
    db = state["db"]
    reading = read_listing(transcript)
    if not reading.complete:
        return {"created": False, "understood": reading.__dict__,
                "error": "the recording did not give both a number of rooms and a price"}

    host = store.host_by_phone(db, phone)
    if host is None:
        host_id = f"h-{secrets.token_hex(3)}"
        store.add_host(db, host_id, host_name or "Nouvel hote", phone,
                       village=reading.place, site=None)
    else:
        host_id = host["id"]

    listing_id = f"L-{secrets.token_hex(3)}"
    store.add_listing(
        db, listing_id, host_id, reading.rooms, reading.price_per_night,
        place=reading.place, breakfast=bool(reading.breakfast),
        description=f"{reading.rooms} room(s) described by the host",
        created_by="voice", confirmed=False,
    )

    message = flow.Outbound(
        to=phone, channel="sms", lang="fr", key="host_listing_created",
        params={
            "rooms": reading.rooms,
            "price": tpl.format_money(reading.price_per_night),
            "cur": "FCFA",
            "meal": " +petit dej" if reading.breakfast else "",
            "place": (reading.place or "")[:28],
        },
    )
    sent = deliver([message], listing_id)
    return {"created": True, "listing_id": listing_id, "confirmed": False,
            "understood": {
                "rooms": reading.rooms, "price_per_night": reading.price_per_night,
                "breakfast": reading.breakfast, "place": reading.place,
                "read_by": reading.read_by, "transcript": reading.transcript,
            },
            "sent": sent}


@app.post("/api/listings/transcript")
async def listing_from_transcript(payload: dict):
    """The same path as a recording, starting from text. Used by the tests."""
    return create_listing_from_transcript(
        (payload.get("transcript") or "").strip(),
        (payload.get("phone") or "").strip(),
        payload.get("host_name") or "",
    )


@app.post("/api/listings/voice")
async def listing_from_voice(phone: str = Form(...), audio: UploadFile = File(...),
                             host_name: str = Form("")):
    """A host records a description of their rooms; the hub transcribes it."""
    voice = state["voice"]
    if not voice.available():
        raise HTTPException(503, "no speech recogniser is installed on this hub")

    suffix = Path(audio.filename or "recording.wav").suffix or ".wav"
    target = Path(tempfile.gettempdir()) / f"karibu-{secrets.token_hex(4)}{suffix}"
    target.write_bytes(await audio.read())
    try:
        transcript = voice.transcribe(target)
    except TranscriptionUnavailable as error:
        raise HTTPException(503, str(error)) from error
    finally:
        target.unlink(missing_ok=True)

    result = create_listing_from_transcript(transcript, phone.strip(), host_name)
    result["transcript"] = transcript
    result["transcription_seconds"] = round(voice.last_latency or 0, 2)
    return result


# --- time ---------------------------------------------------------------------


@app.post("/api/tick")
def tick(at: str | None = None):
    """Run the time-driven steps: the two-hour timeout and the reminder."""
    db = state["db"]
    now = datetime.fromisoformat(at) if at else datetime.now()
    actions = []
    for row in store.bookings_awaiting(db):
        listing = store.get_listing(db, row["listing_id"])
        current = row_to_booking(row, listing)
        updated, messages = flow.on_tick(current, now)
        if messages or updated.state != current.state:
            store.save_booking(db, updated, read_by=row["read_by"])
            actions.append({"ref": updated.ref, "state": updated.state.value,
                            "sent": deliver(messages, updated.ref)})
    return {"at": now.isoformat(timespec="seconds"), "actions": actions}


# --- the tourism office -------------------------------------------------------


@app.get("/api/stats")
def stats():
    db = state["db"]
    rows = [dict(r) for r in store.all_bookings(db)]
    listings = [dict(r) for r in store.all_listings(db)]
    confirmed = [r for r in rows if r["state"] == "confirmed"]
    nights_sold = sum(r["nights"] for r in confirmed)
    revenue = sum(r["price_total"] for r in confirmed)
    by_state: dict[str, int] = {}
    for r in rows:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    rooms = sum(l["rooms"] for l in listings) or 1
    return {
        "listings": len(listings),
        "rooms": rooms,
        "bookings": len(rows),
        "by_state": by_state,
        "nights_sold": nights_sold,
        "revenue": revenue,
        "currency": listings[0]["currency"] if listings else "FCFA",
        "confirmation_rate": round(len(confirmed) / len(rows), 2) if rows else 0.0,
        "recent": rows[:10],
        "catalogue": listings,
    }


@app.get("/api/messages")
def messages(limit: int = 40):
    return {"messages": [dict(m) for m in store.recent_messages(state["db"], limit)]}


# --- pages --------------------------------------------------------------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard_page():
    target = STATIC_DIR / "dashboard.html"
    return FileResponse(target) if target.exists() else {"see": "/docs"}


@app.get("/visitor")
def visitor_page():
    target = STATIC_DIR / "visitor.html"
    return FileResponse(target) if target.exists() else {"see": "/docs"}
