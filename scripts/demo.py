"""Walk the Karibu demo against a running hub and time every step.

This is the scenario the video shows, in order, with the real messages and the
real latency printed as they happen. Run the hub first:

    uvicorn hub.app:app --port 8000
    python scripts/demo.py
"""

from __future__ import annotations

import sys
import time

import httpx

HUB = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
HOST_PHONE = "+237600000001"
LISTING = "L-bafang-01"

KOREAN = "10월 12일부터 2박, 2명 가능한가요? 아침 식사 포함인가요?"
RELATIVE = "we would like to come around the harvest festival, 3 nights, 2 people"

BAR = "─" * 72


def show(title: str) -> None:
    print(f"\n{BAR}\n  {title}\n{BAR}")


def timed(method: str, path: str, **kwargs):
    started = time.perf_counter()
    response = httpx.request(method, f"{HUB}{path}", timeout=180, **kwargs)
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    return response.json(), elapsed


def print_messages(sent):
    for message in sent:
        who = "HOST  (SMS)" if message["channel"] == "sms" else "VISITOR (web)"
        extra = f"  [{message['segments']} segment]" if message["channel"] == "sms" else ""
        print(f"  -> {who} [{message['lang']}]{extra}\n     {message['text']}")


def main() -> None:
    health, _ = timed("GET", "/health")
    show("Karibu hub")
    print(f"  gateway: {health['gateway']}   model: {health['model']}   "
          f"reachable: {health['model_reachable']}")

    # 1. the visitor writes in Korean
    show("1. A Korean visitor writes to a guesthouse with no website")
    print(f"  VISITOR: {KOREAN}")
    body, seconds = timed("POST", "/api/requests", json={
        "listing_id": LISTING, "message": KOREAN, "lang": "ko", "visitor_name": "Mme Kim",
    })
    understood = body["understood"]
    print(f"\n  understood in {seconds:.2f}s: arrival {understood['check_in']}, "
          f"{understood['nights']} nights, {understood['guests']} guests, "
          f"breakfast {understood['breakfast']}")
    print(f"  read by: {understood['read_by']}")
    print()
    print_messages(body["sent"])
    ref = body["ref"]

    # 2. the host answers from a basic phone
    show("2. The host answers with one character")
    print("  HOST: 1")
    body, seconds = timed("POST", "/api/sms/simulate",
                          json={"from": HOST_PHONE, "text": "1"})
    print(f"\n  handled in {seconds:.2f}s, booking {body['ref']} is {body['state']}\n")
    print_messages(body["sent"])

    # 3. a host who does not answer with a digit
    show("3. A host who answers like a human, not like a form")
    for reply in ("Oui merci", "je ne sais pas"):
        # A fresh request each time, so each reply is read on an open booking.
        timed("POST", "/api/requests", json={
            "listing_id": LISTING, "message": KOREAN, "lang": "ko",
        })
        print(f"  HOST: {reply}")
        body, seconds = timed("POST", "/api/sms/simulate",
                              json={"from": HOST_PHONE, "text": reply})
        understood_as = body.get("understood")
        outcome = body["sent"][0]["template"] if body["sent"] else "nothing sent"
        print(f"    read as: {understood_as!r}  ->  {body['state']}, "
              f"{outcome} ({seconds:.2f}s)")

    # 4. a message the rules cannot read, where the small model helps
    show("4. A message no rule can read, where the 1B model is asked")
    print(f"  VISITOR: {RELATIVE}")
    response = httpx.post(f"{HUB}/api/requests", timeout=180, json={
        "listing_id": LISTING, "message": RELATIVE, "lang": "en",
    })
    body = response.json()
    understood = body["understood"]
    print(f"\n  arrival {understood['check_in']}, {understood['nights']} nights, "
          f"{understood['guests']} guests")
    print(f"  read by: {understood['read_by']}")
    if response.status_code == 422:
        print("  no date could be read, so nothing is sent to the host and the")
        print("  visitor is asked again. Karibu does not guess a date.")

    # 5. what the tourism office sees
    show("5. What the tourism office sees")
    stats, seconds = timed("GET", "/api/stats")
    print(f"  listings {stats['listings']}   rooms {stats['rooms']}   "
          f"bookings {stats['bookings']}   nights sold {stats['nights_sold']}")
    print(f"  revenue {stats['revenue']} {stats['currency']}   "
          f"confirmation rate {stats['confirmation_rate']}")
    print(f"  by state: {stats['by_state']}   ({seconds:.2f}s)")

    catalogue, seconds = timed("GET", "/api/catalogue.json")
    item = catalogue["providers"][0]["items"][0]
    print(f"\n  open catalogue: {catalogue['providers'][0]['descriptor']['name']}, "
          f"{item['price']['value']} {item['price']['currency']}/{item['price']['unit']}, "
          f"booked by {item['fulfillment']['channel']}  ({seconds:.2f}s)")
    print(f"\n  booking reference from step 1: {ref}\n")


if __name__ == "__main__":
    main()
