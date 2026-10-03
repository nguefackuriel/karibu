# Karibu

**A guesthouse owner with a basic phone takes a booking from a Korean visitor, in French, for the price of one SMS.**

No app to install, no smartphone, no bank card, and no internet on the host's
side. Built by team **LeKontinent** for the World Bank *Small AI for
Development* hackathon, tourism track, 3–4 October 2026.

---

## The problem

Around parks, waterfalls and heritage sites, the guesthouses, guides and
artisans who actually receive visitors do not exist online. No website, no
booking, no shared language with the traveller. Every booking platform assumes
a smartphone, a steady connection and a card, then takes a commission. The
money stays with intermediaries in the capital, and the tourism office has no
idea what happens on its own territory.

Karibu gives those hosts a booking system that fits in a text message.

## What it does

```
Visitor (any language, web page)          Host (basic phone, SMS)
        │                                          ▲
        │  10월 12일부터 2박, 2명 가능한가요?          │  Karibu: demande 2n 12-14 oct,
        │                                          │  2 pers +petit dej. Total 16000
        ▼                                          │  FCFA. Repondre 1=OUI 2=NON
   ┌────────────────────────────────────────────┐  │  3=AUTRE DATE
   │  Karibu hub — one laptop or Raspberry Pi   │──┘
   │  rules → small model → SQLite → SMS        │◄─── 1
   └────────────────────────────────────────────┘
        │
        ▼  확정되었습니다. 10월 12일-14일, 2명, 조식 포함, 16000 FCFA.
```

1. **The host signs up by voice.** They describe their rooms out loud. Whisper
   transcribes it on the hub, rules read the rooms, the price and the place, and
   the host confirms by texting `1`. Nothing is public until they do.
2. **A visitor writes in their own language.** Korean, English or French, on a
   plain web page.
3. **The host gets one SMS in French** and answers with a single character.
4. **The visitor gets a confirmation in their own language**, and the host a
   reminder the day before arrival.
5. **The tourism office gets a dashboard and an open catalogue**, so the rooms
   can be listed by any destination portal.

## The decision that shapes everything

**The model never writes the host's message, and never reads a date.**

A one-billion-parameter model is small enough for a Raspberry Pi and too small
to be trusted with a booking. Asked for *"du 20 au 23 octobre"* it answered the
23rd. Asked about a message that never mentioned food, it said breakfast was
included. Every time.

So Karibu reads dates, nights, head counts, prices and meals with rules, in
Korean, French and English, including relative dates like *next Friday* and
numbers spoken as words like *huit mille*. The model is asked only for what the
rules could not read, it can never overwrite them, and its answers are
range-checked before use. When neither can read a date, Karibu says so instead
of guessing.

Every outgoing message is then built from a fixed template with those values
dropped in, so a price or a date cannot be mistranslated. The host confirms
before any booking exists.

| Path | Median | What it reads |
| --- | --- | --- |
| Rules | 0.1 ms | Every field, in all the demo messages |
| 1B model | ~2.6 s | Only the blanks the rules left |

Full numbers, including the cost per booking, are in [docs/measurements.md](docs/measurements.md).

## Setup

Needs Python 3.12 and [Ollama](https://ollama.com). Speech recognition is
optional; everything else works without it.

```bash
git clone https://github.com/nguefackuriel/karibu.git && cd karibu
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
ollama pull gemma3:1b
./scripts/start.sh
```

Then open <http://127.0.0.1:8000/visitor> to book, and
<http://127.0.0.1:8000/> for the tourism office.

To watch the whole scenario in the terminal:

```bash
python scripts/demo.py
```

### Sending a real SMS

Without a key, Karibu prints each SMS to the terminal and the demo runs
anywhere. To send through the Africa's Talking sandbox instead, which reaches
their simulator rather than a real handset and costs nothing:

```bash
cp .env.example .env        # then paste your sandbox API key into it
python scripts/check_sms.py # sends one message and reports what the operator said
```

The key lives at **account.africastalking.com → your sandbox app → Settings →
API Key**. Nothing else changes: the hub picks the gateway up at startup, and
`/health` reports `sms_configured` and which gateway is live.

### Receiving the host's replies

Outgoing SMS needs only the key. Incoming SMS is a webhook, so the operator has
to reach this machine:

```bash
./scripts/tunnel.sh        # prints a public https address
```

Run the hub with `./scripts/start.sh`, not a bare `uvicorn`: a bare one takes
whichever Python is first on PATH, which is usually not the one holding this
project's packages.

Two things are needed on the Africa's Talking side, and both are easy to miss:

1. **A shortcode.** Create one in the sandbox app under SMS. Replies cannot go
   back to the alphanumeric sender ID the message appears to come from, so
   without a shortcode there is nowhere for the host to answer.
2. **The incoming-messages callback**, set to the address the script prints,
   ending in `/api/sms/inbound`. This is a different field from the delivery
   report callback.

The address changes every time the tunnel restarts, so re-paste it then. In the
simulator, send the reply to the shortcode, not to the sender ID. Without any of
this, host replies still work through `/api/sms/simulate`, which is what
`scripts/demo.py` uses.

## Tests

```bash
python -m pytest -m "not slow"   # 138 tests, no model and no network needed
python -m pytest                 # adds one test against a real recording
```

The suite replays whole bookings without a phone: the request, a host who
answers `1`, one who writes `Oui merci`, one who writes something unreadable,
one who never answers, refusals, other dates and cancellations. One test asserts
that **every host message fits a single 160-character GSM-7 SMS segment**, so a
change to the wording cannot quietly double what the host pays.

## What is real and what is simulated

**Real**, running on the machine: the booking flow, the rules, the 1B model, the
speech recognition, the SQLite database, the visitor page, the dashboard, the
open catalogue and every measurement in `docs/measurements.md`. The outgoing SMS
is a real API call: Africa's Talking accepts each message and delivers it to
their simulator, and the hub records whether the operator took it.

**Simulated, and said plainly:**

- **Mobile money.** The confirmation tells the visitor to pay on arrival. No
  payment is taken.
- **The Raspberry Pi.** The demo runs on a laptop, CPU only, and the timings are
  reported on CPU so a Pi is a fair extrapolation. Not yet run on the hardware.
- **The handset.** Messages reach the Africa's Talking simulator, which is a web
  page standing in for a phone, not a paid short code on a real network.
- **The network.** Both directions are real API traffic through Africa's
  Talking, verified end to end: a Korean request produced a French SMS that
  arrived on the simulated handset, the reply `1` came back over their
  incoming-messages callback, and the booking confirmed itself. What is
  simulated is the handset and the operator's network, not the integration.
- **The host.** `Nathalie` in `hub/seed.py` is the host in the pitch. The
  village (Bafang) and the site (the Metché falls) are real. Her surname and
  photograph stay out until she agrees to them.

## Acknowledged trade-offs

- **160 characters instead of a screen.** Every question to the host is closed
  and every answer is one character. Rich choice is given up for a message that
  costs one segment and shows on any handset.
- **Rules instead of a bigger model.** Rules do not generalise; they had to be
  written for each language. In exchange, the dates are right and the answer
  arrives in a millisecond.
- **The host waits.** Confirmation is asynchronous, and the visitor is told to
  allow two hours. After that the request expires and the visitor is freed.
- **Three languages, not a hundred.** Korean, French and English are read by
  rule. Another language means another small table, not a retrained model.
- **No booking is final without a human.** The model can be wrong; the host is
  the check. That is slower than an automatic confirmation, and it is the only
  version worth deploying.

## Repository

| Folder | What it holds |
| --- | --- |
| `hub/` | The server: booking flow, SMS templates, SQLite, and the rules and model services |
| `channels/` | The way out: console gateway for the demo, Africa's Talking for real SMS |
| `dashboard/static/` | The visitor page and the tourism office dashboard, plain HTML |
| `scripts/` | `demo.py` walks the scenario, `measure.py` regenerates the numbers |
| `docs/` | Measurements, and the demo scenario |
| `tests/` | 139 tests, including one against a real recording |

Licence: MIT.
