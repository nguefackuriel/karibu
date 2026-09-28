"""Turning a traveller's message into a booking request.

Two readers, in this order. The rules in `dates` read what can be read with
certainty, in Korean, French and English. The small model is then asked only
for the fields the rules left empty, and it is never allowed to overwrite them.
Whatever comes out, the host sees it in plain words and confirms before a
booking exists.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from .dates import DateReading, read as read_rules
from .ollama import ModelUnavailable, Ollama

MODEL_PROMPT = """You read a traveller's message to a small guesthouse.
Today is {today}.

Return ONLY a JSON object with these keys, using null when the message does not say:
  check_in: the arrival date as YYYY-MM-DD
  nights: how many nights, as a number
  guests: how many people, as a number

Do not explain. If the message names no date at all, use null for check_in.

Message: {message}"""

CRITICAL = ("check_in", "nights", "guests")


@dataclass
class Extraction:
    check_in: date | None = None
    nights: int | None = None
    guests: int | None = None
    breakfast: bool | None = None
    note: str | None = None
    read_by: dict[str, str] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return all(getattr(self, name) is not None for name in CRITICAL)

    @property
    def needs_host_care(self) -> bool:
        """True when the model supplied something a rule could not confirm."""
        return any(self.read_by.get(name) == "model" for name in CRITICAL)

    def as_dict(self) -> dict:
        out = asdict(self)
        out["check_in"] = self.check_in.isoformat() if self.check_in else None
        out["complete"] = self.complete
        out["needs_host_care"] = self.needs_host_care
        return out


def _coerce_int(value, low: int, high: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _coerce_date(value, today: date) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    # A model that hallucinates a date in the past, or years ahead, is ignored.
    if parsed < today or (parsed - today).days > 400:
        return None
    return parsed


def extract(
    message: str,
    today: date | None = None,
    model: Ollama | None = None,
    defaults: dict | None = None,
) -> Extraction:
    """Read a message. `model` may be None to run on rules alone."""
    today = today or date.today()
    reading: DateReading = read_rules(message, today)

    out = Extraction(
        check_in=reading.check_in,
        nights=reading.nights,
        guests=reading.guests,
        breakfast=reading.breakfast,
        note=message.strip() or None,
        read_by=dict(reading.read_by),
    )

    missing = [name for name in CRITICAL if getattr(out, name) is None]
    if missing and model is not None:
        try:
            suggestion = model.generate_json(
                MODEL_PROMPT.format(today=today.isoformat(), message=message)
            )
        except ModelUnavailable:
            suggestion = {}

        if out.check_in is None:
            candidate = _coerce_date(suggestion.get("check_in"), today)
            if candidate:
                out.check_in = candidate
                out.read_by["check_in"] = "model"
        if out.nights is None:
            candidate = _coerce_int(suggestion.get("nights"), 1, 30)
            if candidate:
                out.nights = candidate
                out.read_by["nights"] = "model"
        if out.guests is None:
            candidate = _coerce_int(suggestion.get("guests"), 1, 20)
            if candidate:
                out.guests = candidate
                out.read_by["guests"] = "model"
        # Breakfast is deliberately not asked of the model: in testing it
        # answered "true" for every message, including ones that never
        # mentioned a meal. The rules read the word or nobody does.

    # Last resort, so a half-read message still reaches the host as a question.
    defaults = defaults or {"nights": 1, "guests": 2, "breakfast": False}
    for name, value in defaults.items():
        if getattr(out, name) is None:
            setattr(out, name, value)
            out.read_by[name] = "default"

    return out
