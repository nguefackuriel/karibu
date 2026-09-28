"""The demo, driven through the API exactly as the video will show it.

No model and no SMS account are needed: the message is written so the rules can
read it, and the gateway keeps every SMS on the machine.
"""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from hub import db as store
from hub import seed

HOST_PHONE = "+237600000001"
KOREAN_REQUEST = "10월 12일부터 2박, 2명 가능한가요? 아침 식사 포함인가요?"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("KARIBU_DB", str(db_path))
    # Pin the host's number so the suite does not depend on a local .env,
    # and blank the API key so a test can never send a real SMS.
    monkeypatch.setenv("KARIBU_HOST_PHONE", HOST_PHONE)
    monkeypatch.setenv("AT_API_KEY", "")
    seed.run(str(db_path))

    from hub.app import app, state
    from channels.gateway import ConsoleGateway

    with TestClient(app) as running:
        state["gateway"] = ConsoleGateway(echo=False)
        state["model"] = None  # rules only, so the tests stay fast and offline
        yield running


def make_request(client, message=KOREAN_REQUEST, lang="ko"):
    response = client.post("/api/requests", json={
        "listing_id": "L-bafang-01", "message": message,
        "lang": lang, "visitor_name": "Mme Kim",
    })
    assert response.status_code == 200, response.text
    return response.json()


# --- the happy path -----------------------------------------------------------


def test_a_korean_request_produces_one_french_sms_to_the_host(client):
    body = make_request(client)

    assert body["state"] == "awaiting_host"
    assert body["understood"]["check_in"].endswith("-10-12")
    assert body["understood"]["nights"] == 2
    assert body["understood"]["guests"] == 2

    sms = [m for m in body["sent"] if m["channel"] == "sms"]
    assert len(sms) == 1
    assert sms[0]["lang"] == "fr"
    assert sms[0]["segments"] == 1, "the host must not pay for two messages"
    assert "1=OUI" in sms[0]["text"]
    assert "16000 FCFA" in sms[0]["text"]


def test_the_host_replies_one_and_the_visitor_is_confirmed_in_korean(client):
    ref = make_request(client)["ref"]

    reply = client.post("/api/sms/simulate", json={"from": HOST_PHONE, "text": "1"})
    assert reply.status_code == 200
    body = reply.json()
    assert body["handled"] and body["state"] == "confirmed" and body["ref"] == ref

    to_visitor = [m for m in body["sent"] if m["channel"] == "web"][0]
    assert to_visitor["lang"] == "ko"
    assert any("가" <= ch <= "힣" for ch in to_visitor["text"])

    status = client.get(f"/api/requests/{ref}").json()
    assert status["state"] == "confirmed"
    assert status["price_total"] == 16000


def test_a_host_writing_oui_is_understood(client):
    make_request(client)
    body = client.post("/api/sms/simulate",
                       json={"from": HOST_PHONE, "text": "Oui merci"}).json()
    assert body["understood"] == "1"
    assert body["state"] == "confirmed"


def test_an_unreadable_reply_gets_one_reprompt(client):
    make_request(client)
    body = client.post("/api/sms/simulate",
                       json={"from": HOST_PHONE, "text": "je ne sais pas"}).json()
    assert body["state"] == "awaiting_host"
    assert body["sent"][0]["template"] == "host_reprompt"


def test_an_sms_from_an_unknown_number_is_ignored(client):
    make_request(client)
    body = client.post("/api/sms/simulate",
                       json={"from": "+237699999999", "text": "1"}).json()
    assert body["handled"] is False


def test_the_africas_talking_webhook_shape_works(client):
    ref = make_request(client)["ref"]
    response = client.post("/api/sms/inbound",
                           data={"from": HOST_PHONE, "to": "12345", "text": "1",
                                 "date": "2026-10-10 09:00:00", "id": "abc"})
    assert response.status_code == 200
    assert response.json()["state"] == "confirmed"


# --- what happens when nobody answers -----------------------------------------


def test_silence_expires_the_request(client):
    ref = make_request(client)["ref"]
    later = (datetime.now() + timedelta(hours=3)).isoformat(timespec="seconds")
    body = client.post(f"/api/tick?at={later}").json()
    assert body["actions"], "the timeout should have fired"
    assert client.get(f"/api/requests/{ref}").json()["state"] == "expired"


# --- a message the rules cannot read ------------------------------------------


def test_a_message_without_a_date_is_refused_rather_than_guessed(client):
    response = client.post("/api/requests", json={
        "listing_id": "L-bafang-01", "message": "bonjour, vous avez de la place ?",
        "lang": "fr",
    })
    assert response.status_code == 422
    assert response.json()["understood"]["check_in"] is None


# --- what the tourism office sees ---------------------------------------------


def test_the_catalogue_is_open_and_readable(client):
    body = client.get("/api/catalogue.json").json()
    provider = body["providers"][0]
    assert provider["descriptor"]["name"] == "Nathalie"
    item = provider["items"][0]
    assert item["price"]["value"] == 8000
    assert item["fulfillment"]["channel"] == "sms"


def test_the_dashboard_counts_a_confirmed_booking(client):
    make_request(client)
    client.post("/api/sms/simulate", json={"from": HOST_PHONE, "text": "1"})
    stats = client.get("/api/stats").json()
    assert stats["bookings"] == 1
    assert stats["by_state"]["confirmed"] == 1
    assert stats["nights_sold"] == 2
    assert stats["revenue"] == 16000


def test_every_message_is_written_down(client):
    ref = make_request(client)["ref"]
    client.post("/api/sms/simulate", json={"from": HOST_PHONE, "text": "1"})
    messages = client.get(f"/api/requests/{ref}").json()["messages"]
    directions = [m["direction"] for m in messages]
    assert directions.count("in") == 2   # the visitor's message and the host's reply
    assert directions.count("out") == 4  # request + ack to each side


# --- a host signing up by voice -----------------------------------------------

NEW_HOST = "+237600000042"
SPOKEN = ("J'ai deux chambres, 8000 francs la nuit avec le petit dejeuner, "
          "c'est a Bafang pres des chutes.")


def test_a_spoken_description_becomes_a_listing_awaiting_confirmation(client):
    body = client.post("/api/listings/transcript", json={
        "transcript": SPOKEN, "phone": NEW_HOST, "host_name": "M. Kamdem",
    }).json()

    assert body["created"] and body["confirmed"] is False
    understood = body["understood"]
    assert understood["rooms"] == 2
    assert understood["price_per_night"] == 8000
    assert understood["breakfast"] is True
    assert "Bafang" in understood["place"]

    sms = body["sent"][0]
    assert sms["channel"] == "sms" and sms["segments"] == 1
    assert "1=OK" in sms["text"] and "8000" in sms["text"]


def test_a_new_listing_is_invisible_until_the_host_confirms(client):
    body = client.post("/api/listings/transcript", json={
        "transcript": SPOKEN, "phone": NEW_HOST,
    }).json()
    listing_id = body["listing_id"]

    catalogue = client.get("/api/catalogue.json").json()
    listed = [i["id"] for p in catalogue["providers"] for i in p["items"]]
    assert listing_id not in listed, "an unconfirmed listing must not be public"

    reply = client.post("/api/sms/simulate",
                        json={"from": NEW_HOST, "text": "1"}).json()
    assert reply["state"] == "listing_confirmed"

    catalogue = client.get("/api/catalogue.json").json()
    listed = [i["id"] for p in catalogue["providers"] for i in p["items"]]
    assert listing_id in listed


def test_a_host_asking_to_correct_leaves_the_listing_unconfirmed(client):
    client.post("/api/listings/transcript", json={"transcript": SPOKEN, "phone": NEW_HOST})
    reply = client.post("/api/sms/simulate",
                        json={"from": NEW_HOST, "text": "2"}).json()
    assert reply["state"] == "listing_needs_correction"
    catalogue = client.get("/api/catalogue.json").json()
    assert len(catalogue["providers"]) == 1, "only the seeded host is public"


def test_a_recording_with_no_price_is_refused(client):
    body = client.post("/api/listings/transcript", json={
        "transcript": "bonjour, j'ai deux chambres", "phone": NEW_HOST,
    }).json()
    assert body["created"] is False
    assert "price" in body["error"]


def test_a_booking_reply_still_wins_over_a_pending_listing(client):
    """A host with both waiting answers the booking, which is the urgent one."""
    client.post("/api/listings/transcript",
                json={"transcript": SPOKEN, "phone": HOST_PHONE})
    make_request(client)
    reply = client.post("/api/sms/simulate",
                        json={"from": HOST_PHONE, "text": "1"}).json()
    assert reply["state"] == "confirmed"
