"""Seed data for the demo.

Placeholder until the real host is confirmed by phone. The village and the site
are real; the name, the phone and the price are stand-ins and are marked as
such in the README so nothing in the pitch claims more than it should.
"""

from __future__ import annotations

import os

from hub import db as store

# The host's number comes from KARIBU_HOST_PHONE so the demo texts whichever
# handset is open in the Africa's Talking simulator.
HOST = {
    "host_id": "h-bafang-01",
    "name": "Mme Tchoua",           # placeholder, to be replaced by the real host
    "phone": os.environ.get("KARIBU_HOST_PHONE", "+237600000001"),
    "village": "Bafang",
    "site": "Chutes de la Metche",
    "lang": "fr",
}

LISTING = {
    "listing_id": "L-bafang-01",
    "host_id": "h-bafang-01",
    "rooms": 2,
    "price_per_night": 8000,
    "currency": "FCFA",
    "breakfast": True,
    "place": "Bafang, pres des chutes",
    "description": "Two rooms in a family guesthouse, breakfast included",
    "created_by": "voice",
    "confirmed": True,
}


def run(path: str | None = None) -> None:
    from hub.app import load_env_file
    load_env_file()
    HOST["phone"] = os.environ.get("KARIBU_HOST_PHONE", HOST["phone"])
    db = store.connect(path or os.environ.get("KARIBU_DB"))
    store.add_host(db, **HOST)
    store.add_listing(db, **LISTING)
    print(f"seeded host {HOST['name']} on {HOST['phone']} "
          f"with listing {LISTING['listing_id']}")
    db.close()


if __name__ == "__main__":
    run()
