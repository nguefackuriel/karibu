# Karibu

The SMS receptionist for tourism micro-enterprises.

A guesthouse owner with a basic phone receives a booking from a foreign visitor, translated on the spot, and confirms by texting `1`. No app, no internet on the host side, no middleman.

Built by team **LeKontinent** (Uriel, Ruth, Rouguiatou) for the World Bank Small AI for Development Hackathon, tourism track, October 3-4, 2026.

## The problem

Around parks, waterfalls and heritage sites, guesthouses, guides and artisans do not exist online. They have no website, no booking system and no common language with the visitor. Booking platforms need a smartphone, a stable connection and a bank card, and they take a commission. The tourism office has no data on what happens on its territory.

## What Karibu does

1. **Sign-up by voice.** The host calls a number and describes the rooms. Karibu turns the recording into a listing and confirms it by SMS.
2. **Visitor request.** The visitor writes in Korean or English on a simple web page. Karibu translates it locally and sends one SMS to the host in French: `Request: 2 nights Oct 12-14, 2 guests, breakfast. Reply 1=YES 2=NO 3=OTHER DATE`.
3. **Confirmation.** The host replies `1`. The visitor gets a confirmation in their own language. The host gets a reminder the day before.
4. **Open catalogue.** Every listing is exported as open JSON for the tourism office, with a dashboard of listings, bookings and occupancy.

## How it runs

One small "hub" runs the AI models. In the demo it is a laptop, CPU only. In real life it is a Raspberry Pi at the tourism office. Hosts reach it by SMS through a gateway. No cloud AI is in the loop.

```
Host (basic phone) <-- SMS --> Gateway (Africa's Talking) <--> Hub (FastAPI + SQLite + small models) <--> Visitor web page / Tourism office dashboard
```

Models: NLLB-200 600M for translation, Gemma 3 1B for extraction, faster-whisper small for voice.

## Repository layout

| Folder | What it holds | Owner |
| --- | --- | --- |
| `hub/` | FastAPI server, SQLite, translation, extraction, voice, booking flow | Uriel |
| `channels/` | SMS and voice gateway (Africa's Talking), webhooks | Rouguiatou |
| `dashboard/` | Visitor web page, tourism office dashboard, catalogue export | Ruth |
| `docs/` | Demo scenario, architecture, measurements, pitch material | Ruth |

## Setup

Five commands, to be filled in as the hub takes shape:

```bash
git clone https://github.com/nguefackuriel/karibu.git
cd karibu
# 3. install dependencies
# 4. download models
# 5. run the hub
```

## What is real and what is simulated

To be written before submission. Real: SMS gateway simulator, translation, extraction, booking flow, voice sign-up, dashboard, catalogue export, measured latency on CPU. Simulated: Mobile Money payment, deployment on a Raspberry Pi.

## How we work

- One branch per person: `uriel`, `ruth`, `rouguiatou`. Open a pull request into `main`. Uriel merges.
- `main` always runs.
- English in code, README and docs. French only in the host-side SMS shown in the demo.
