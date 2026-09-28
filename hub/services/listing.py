"""Reading a listing out of what a host said.

The host calls and describes their rooms in their own words: "J'ai deux
chambres, huit mille francs la nuit avec le petit dejeuner, c'est a Bafang pres
des chutes." Rooms and price are money, so they are read by rule from the
spoken numbers. The host then confirms the result by SMS before the listing is
visible to anybody.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import numbers
from .dates import NEGATIONS, normalise

ROOM_WORDS = ("chambre", "chambres", "piece", "pieces", "room", "rooms")
MONEY_WORDS = ("franc", "francs", "fcfa", "cfa", "nuit", "nuits", "night", "nights")
BREAKFAST_WORDS = ("petit dejeuner", "petit dej", "petitdej", "breakfast", "dejeuner")

PLACE_PATTERNS = (
    r"c'est (?:a|au|aux) (.+)",
    r"(?:situe|situee|situes) (?:a|au|aux) (.+)",
    r"(?:je suis|nous sommes|on est) (?:a|au|aux) (.+)",
    r"\ba (.+?(?:pres|proche).+)",
)


@dataclass
class ListingReading:
    rooms: int | None = None
    price_per_night: int | None = None
    breakfast: bool | None = None
    place: str | None = None
    transcript: str = ""
    read_by: dict[str, str] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return self.rooms is not None and self.price_per_night is not None


def _read_place(transcript: str) -> str | None:
    """The last thing a host says is usually where they are."""
    flat = normalise(transcript)
    for pattern in PLACE_PATTERNS:
        match = re.search(pattern, flat)
        if match:
            place = match.group(1).strip(" .,;")
            if 2 < len(place) <= 80:
                # Give it back with the original capitalisation where we can.
                start = normalise(transcript).find(place)
                if start != -1 and len(transcript) >= start + len(place):
                    return transcript[start:start + len(place)].strip(" .,;")
                return place
    return None


def read(transcript: str) -> ListingReading:
    out = ListingReading(transcript=transcript.strip())
    tokens = numbers.tokenise(transcript)

    for value, _, end in numbers.runs(transcript):
        following = tokens[end + 1:end + 4]
        if out.rooms is None and any(word in ROOM_WORDS for word in following):
            if 1 <= value <= 60:
                out.rooms = value
                out.read_by["rooms"] = "rule"
            continue
        if out.price_per_night is None and any(word in MONEY_WORDS for word in following):
            if 100 <= value <= 5_000_000:
                out.price_per_night = value
                out.read_by["price_per_night"] = "rule"

    flat = normalise(transcript)
    for word in BREAKFAST_WORDS:
        position = flat.find(word)
        if position == -1:
            continue
        window = flat[max(0, position - 20):position + len(word) + 10]
        out.breakfast = not any(negation in window for negation in NEGATIONS)
        out.read_by["breakfast"] = "rule"
        break

    place = _read_place(transcript)
    if place:
        out.place = place
        out.read_by["place"] = "rule"

    return out
