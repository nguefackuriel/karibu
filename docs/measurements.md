# Measurements

Measured on x86_64 CPU, no GPU, no network call in the booking
path. Re-run with `python scripts/measure.py`.

Machine: Darwin 24.6.0 on x86_64,
Python 3.12.14. Model runner: gemma3:1b.

## How long a booking takes

| Step | Median | 95th percentile | Worst |
| --- | --- | --- | --- |
| Read a message the rules can read | 0.1 ms | 0.5 ms | 3.5 ms |
| Read a message needing the 1B model | 1564.5 ms | 1810.3 ms | 7089.8 ms |

The rules answer in well under a millisecond. The model takes about 1.6 seconds, some 15,645 times longer, which is why it is asked last and only for what the rules left blank. On every message in the demo the rules read each field, so the
model is not called at all and a booking leaves for the host in milliseconds.

## Understanding a host who speaks instead of typing
| Step | Value |
| --- | --- |
| Recording length | 5.7 s |
| Transcription on CPU | 3.7 s |
| Speed against real time | 1.5x |
| Rooms, price, meal and place all read | yes |

Whisper small, int8, on the hub's own processor. No audio leaves the
machine, which matters because a host is recorded at home.

## What one exchange costs the host

| Item | Value |
| --- | --- |
| Longest host SMS | 113 characters (`host_listing_created`) |
| One SMS segment | 160 characters |
| Segments per host message | 1 |
| SMS per completed booking | 4 |
| Cost per completed booking | about 0.08 USD at 0.02 USD per SMS |
| Hub for one tourism office | about 80 USD, one time |

Every host message is checked against the GSM-7 character set, so none of them
silently becomes a two-segment message and doubles the price.

## How small the whole thing is

| Item | Value |
| --- | --- |
| Language model on disk | 815.0 MB |
| Python in the hub and channels | 1966 lines |
| Runtime dependencies | FastAPI, uvicorn, httpx (SQLite is in the standard library) |
| Database | one SQLite file |
| Internet needed to take a booking | none |

## What is not measured here

Battery life, since the hub is mains powered. Delivery time of the SMS itself,
which belongs to the mobile operator, not to Karibu. Both are named in the
trade-offs slide instead.
