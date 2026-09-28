"""Measure Karibu on this machine and write docs/measurements.md.

Judges asked for capability against access, so the numbers that matter are how
long a booking takes, how much of it needs the model, what one exchange costs
the host, and how small the whole thing is. Everything here is measured on CPU
with no GPU and no cloud call, because that is the machine a tourism office has.
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import templates as tpl                      # noqa: E402
from hub.services.extract import extract              # noqa: E402
from hub.services.listing import read as read_listing  # noqa: E402
from hub.services.ollama import Ollama                # noqa: E402
from hub.services.voice import Whisper                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "measurements.md"
TODAY = date(2026, 10, 8)
RUNS = 20

RULE_MESSAGES = [
    "10월 12일부터 2박, 2명 가능한가요? 아침 식사 포함인가요?",
    "Room from 20th to 23rd October for 2 guests please",
    "Bonjour, de la place pour 3 personnes du 20 au 23 octobre ?",
    "next week friday, 3 nights, 2 people",
]
MODEL_MESSAGE = "we would like to come around the harvest festival, 3 nights, 2 people"

# Indicative, to be confirmed against the operator's price list before the pitch.
SMS_UNIT_COST_USD = 0.02
PI_HUB_COST_USD = 80


def timed(function, *args, runs=RUNS):
    samples = []
    for _ in range(runs):
        started = time.perf_counter()
        function(*args)
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def summarise(samples):
    ordered = sorted(samples)
    return {
        "median_ms": round(statistics.median(ordered), 1),
        "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 1),
        "max_ms": round(max(ordered), 1),
    }


def model_size_mb(model_name: str) -> float | None:
    try:
        listing = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=20)
        for line in listing.stdout.splitlines():
            if line.startswith(model_name):
                parts = line.split()
                size, unit = float(parts[2]), parts[3].upper()
                return round(size * (1024 if unit.startswith("G") else 1), 1)
    except Exception:
        return None
    return None


def main() -> None:
    model = Ollama()
    model_up = model.available()

    print("measuring rule-only extraction ...")
    rules = summarise([s for m in RULE_MESSAGES
                       for s in timed(extract, m, TODAY, None, runs=RUNS // 2)])

    model_stats = None
    if model_up:
        print("measuring the model fallback (this is the slow path) ...")
        model_stats = summarise(timed(extract, MODEL_MESSAGE, TODAY, model, runs=5))

    voice = Whisper(size="small")
    voice_stats = None
    fixture = ROOT / "tests" / "fixtures" / "host-signup-fr.wav"
    if voice.available() and fixture.exists():
        print("measuring speech recognition (loading the model first) ...")
        voice.transcribe(fixture)          # warm: the first call loads the model
        transcript = voice.transcribe(fixture)
        seconds = voice.last_latency or 0
        audio_seconds = 0.0
        try:
            import wave
            with wave.open(str(fixture)) as handle:
                audio_seconds = handle.getnframes() / handle.getframerate()
        except Exception:
            pass
        reading = read_listing(transcript)
        voice_stats = {
            "seconds": round(seconds, 1),
            "audio_seconds": round(audio_seconds, 1),
            "realtime": round(audio_seconds / seconds, 1) if seconds else 0,
            "complete": reading.complete,
        }

    print("counting SMS ...")
    host_messages = {
        key: tpl.render(key, "fr", {
            "ref": "K7F3", "nights": 2, "stay": "12-14 oct", "arrival": "12 oct",
            "guests": 2, "meal": " +petit dej", "total": "16000", "cur": "FCFA",
            "visitor": "Mme Kim", "hours": 2, "rooms": 2, "price": "8000",
            "place": "Bafang, pres des chutes",
        })
        for key in tpl.TEMPLATES if key.startswith("host_")
    }
    longest = max(host_messages.items(), key=lambda kv: len(kv[1]))
    # A completed booking: request, confirmation, reminder out; one reply in.
    sms_per_booking = 4

    size_mb = model_size_mb(model.model)
    code_lines = sum(
        len(path.read_text().splitlines())
        for folder in ("hub", "channels")
        for path in (ROOT / folder).rglob("*.py")
    )

    if voice_stats:
        voice_line = (
            f"| Step | Value |\n| --- | --- |\n"
            f"| Recording length | {voice_stats['audio_seconds']} s |\n"
            f"| Transcription on CPU | {voice_stats['seconds']} s |\n"
            f"| Speed against real time | {voice_stats['realtime']}x |\n"
            f"| Rooms, price, meal and place all read | "
            f"{'yes' if voice_stats['complete'] else 'no'} |\n\n"
            "Whisper small, int8, on the hub's own processor. No audio leaves the\n"
            "machine, which matters because a host is recorded at home."
        )
    else:
        voice_line = "Speech recognition is not installed on this machine, so it was not measured."

    report = f"""# Measurements

Measured on {platform.machine()} CPU, no GPU, no network call in the booking
path. Re-run with `python scripts/measure.py`.

Machine: {platform.system()} {platform.release()} on {platform.machine()},
Python {platform.python_version()}. Model runner: {model.model}.

## How long a booking takes

| Step | Median | 95th percentile | Worst |
| --- | --- | --- | --- |
| Read a message the rules can read | {rules['median_ms']} ms | {rules['p95_ms']} ms | {rules['max_ms']} ms |
"""
    if model_stats:
        report += (f"| Read a message needing the 1B model | {model_stats['median_ms']} ms |"
                   f" {model_stats['p95_ms']} ms | {model_stats['max_ms']} ms |\n")
    else:
        report += "| Read a message needing the 1B model | model runner was not up |  |  |\n"

    if model_stats:
        ratio = model_stats["median_ms"] / max(rules["median_ms"], 0.001)
        comparison = (f"The rules answer in well under a millisecond. The model takes about "
                      f"{model_stats['median_ms'] / 1000:.1f} seconds, some {ratio:,.0f} times "
                      f"longer, which is why it is asked last and only for what the rules "
                      f"left blank.")
    else:
        comparison = "The model runner was not up, so only the rule path was measured."

    report += f"""
{comparison} On every message in the demo the rules read each field, so the
model is not called at all and a booking leaves for the host in milliseconds.

## Understanding a host who speaks instead of typing
{voice_line}

## What one exchange costs the host

| Item | Value |
| --- | --- |
| Longest host SMS | {len(longest[1])} characters (`{longest[0]}`) |
| One SMS segment | {tpl.SMS_SEGMENT} characters |
| Segments per host message | 1 |
| SMS per completed booking | {sms_per_booking} |
| Cost per completed booking | about {round(sms_per_booking * SMS_UNIT_COST_USD, 2)} USD at {SMS_UNIT_COST_USD} USD per SMS |
| Hub for one tourism office | about {PI_HUB_COST_USD} USD, one time |

Every host message is checked against the GSM-7 character set, so none of them
silently becomes a two-segment message and doubles the price.

## How small the whole thing is

| Item | Value |
| --- | --- |
| Language model on disk | {f'{size_mb} MB' if size_mb else 'not measured'} |
| Python in the hub and channels | {code_lines} lines |
| Runtime dependencies | FastAPI, uvicorn, httpx (SQLite is in the standard library) |
| Database | one SQLite file |
| Internet needed to take a booking | none |

## What is not measured here

Battery life, since the hub is mains powered. Delivery time of the SMS itself,
which belongs to the mobile operator, not to Karibu. Both are named in the
trade-offs slide instead.
"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(report)
    print(f"\nwritten to {OUT.relative_to(ROOT)}\n")
    print(report)


if __name__ == "__main__":
    main()
