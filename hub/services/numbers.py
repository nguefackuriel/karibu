"""Reading numbers written as French words.

Speech recognition returns "huit mille", not 8000. A host saying their nightly
price out loud is the one number in Karibu that absolutely must be right, so it
is parsed here by rule and never by a model.
"""

from __future__ import annotations

import re

from .dates import normalise

UNITS = {
    "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
    "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
}
TENS = {"vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60}
SCALES = {"cent": 100, "cents": 100, "mille": 1000, "milles": 1000}
JOINERS = {"et", "de", "a"}

NUMBER_TOKENS = set(UNITS) | set(TENS) | set(SCALES) | {"quatrevingt"}


def tokenise(text: str) -> list[str]:
    """Normalise and split, folding 'quatre-vingt' into a single token.

    Without that fold, accumulation would read 'quatre vingt' as four plus
    twenty instead of eighty.
    """
    flat = normalise(text).replace("-", " ")
    # French writes eight thousand as "8 000", so a space inside a numeral is a
    # thousands separator, not a gap between two numbers.
    previous = None
    while previous != flat:
        previous = flat
        flat = re.sub(r"(\d)\s+(\d{3})(?!\d)", r"\1\2", flat)
    flat = re.sub(r"\bquatre\s+vingts?\b", "quatrevingt", flat)
    flat = re.sub(r"\bdix\s*[-\s]\s*(sept|huit|neuf)\b", r"dix \1", flat)
    return [token for token in re.split(r"[^a-z0-9]+", flat) if token]


def is_number_token(token: str) -> bool:
    return token.isdigit() or token in NUMBER_TOKENS


def value_of(tokens: list[str]) -> int | None:
    """Turn a run of number tokens into one integer."""
    total, current, seen = 0, 0, False
    for token in tokens:
        if token.isdigit():
            current += int(token)
            seen = True
        elif token == "quatrevingt":
            current += 80
            seen = True
        elif token in UNITS:
            current += UNITS[token]
            seen = True
        elif token in TENS:
            current += TENS[token]
            seen = True
        elif token in SCALES:
            scale = SCALES[token]
            if scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
            seen = True
    return total + current if seen else None


def runs(text: str) -> list[tuple[int, int, int]]:
    """Every number in the text as (value, first token index, last token index)."""
    tokens = tokenise(text)
    found: list[tuple[int, int, int]] = []
    index = 0
    while index < len(tokens):
        if not is_number_token(tokens[index]):
            index += 1
            continue
        start = index
        while index < len(tokens) and (
            is_number_token(tokens[index])
            or (tokens[index] in JOINERS
                and index + 1 < len(tokens) and is_number_token(tokens[index + 1]))
        ):
            index += 1
        value = value_of([t for t in tokens[start:index] if t not in JOINERS])
        if value is not None:
            found.append((value, start, index - 1))
    return found


def parse(text: str) -> int | None:
    """The single number in a short phrase, or None."""
    found = runs(text)
    return found[0][0] if found else None
