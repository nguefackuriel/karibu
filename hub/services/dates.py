"""Reading dates, counts and meals out of a traveller's message, with rules.

A one-billion-parameter model is small enough to run on a Raspberry Pi and too
small to be trusted with a date. Asked for "du 20 au 23 octobre" it answered
the 23rd. A wrong date is a host who turns up on the wrong day, so dates,
nights and head counts are read by rules here, in Korean, French and English.
Whatever the rules cannot read is left empty for the model to suggest, and the
host still confirms before any booking exists.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

MONTHS: dict[str, int] = {}
for index, names in enumerate(
    [
        ("january", "jan", "janvier", "janv"),
        ("february", "feb", "fevrier", "fevr", "fev"),
        ("march", "mar", "mars"),
        ("april", "apr", "avril", "avr"),
        ("may", "mai"),
        ("june", "jun", "juin"),
        ("july", "jul", "juillet", "juil"),
        ("august", "aug", "aout"),
        ("september", "sep", "sept", "septembre"),
        ("october", "oct", "octobre"),
        ("november", "nov", "novembre"),
        ("december", "dec", "decembre"),
    ],
    start=1,
):
    for name in names:
        MONTHS[name] = index

MONTH_WORDS = "|".join(sorted(MONTHS, key=len, reverse=True))

WEEKDAYS: dict[str, int] = {}
for index, names in enumerate(
    [
        ("monday", "mon", "lundi", "\uc6d4\uc694\uc77c"),
        ("tuesday", "tue", "tues", "mardi", "\ud654\uc694\uc77c"),
        ("wednesday", "wed", "mercredi", "\uc218\uc694\uc77c"),
        ("thursday", "thu", "thur", "thurs", "jeudi", "\ubaa9\uc694\uc77c"),
        ("friday", "fri", "vendredi", "\uae08\uc694\uc77c"),
        ("saturday", "sat", "samedi", "\ud1a0\uc694\uc77c"),
        ("sunday", "sun", "dimanche", "\uc77c\uc694\uc77c"),
    ]
):
    for name in names:
        WEEKDAYS[name] = index

NEXT_WEEK_WORDS = ("next week", "semaine prochaine", "\ub2e4\uc74c \uc8fc", "\ub2e4\uc74c\uc8fc")
TOMORROW_WORDS = ("tomorrow", "demain", "\ub0b4\uc77c")
AFTER_TOMORROW_WORDS = ("day after tomorrow", "apres-demain", "apres demain", "\ubaa8\ub808")
WEEKEND_WORDS = ("this weekend", "ce week-end", "ce weekend", "\uc774\ubc88 \uc8fc\ub9d0", "\uc8fc\ub9d0")

BREAKFAST_WORDS = ("petit dejeuner", "petit dej", "petitdej", "breakfast", "아침")
NEGATIONS = ("sans", "without", "no ", "not ", "pas de", "없이", "안 ")


def strip_accents(text: str) -> str:
    """Drop Latin accents and leave every other script intact.

    NFKD would also pull a Korean syllable apart into its jamo, which makes
    "10\uc6d4" unreadable to the patterns below. Decomposing and recomposing
    around the combining-mark filter keeps Hangul whole.
    """
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", without_marks)


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def _resolve_year(month: int, day: int, today: date) -> date:
    """A message saying '12 October' means the next 12 October, not a past one."""
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return date(today.year, month, day)


@dataclass
class DateReading:
    check_in: date | None = None
    nights: int | None = None
    guests: int | None = None
    breakfast: bool | None = None
    read_by: dict[str, str] = field(default_factory=dict)

    def mark(self, field_name: str, how: str) -> None:
        self.read_by[field_name] = how


def _find_day_month(text: str) -> list[tuple[int, int]]:
    """Every explicit day+month pair, in the order written."""
    found: list[tuple[int, int, int]] = []  # (position, day, month)

    # Korean: 10월 12일
    for m in re.finditer(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
        found.append((m.start(), int(m.group(2)), int(m.group(1))))

    # "12 octobre", "12 oct"
    for m in re.finditer(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_WORDS})\b", text):
        found.append((m.start(), int(m.group(1)), MONTHS[m.group(2)]))

    # "october 12", "oct 12th"
    for m in re.finditer(rf"\b({MONTH_WORDS})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", text):
        found.append((m.start(), int(m.group(2)), MONTHS[m.group(1)]))

    # "12/10" or "12-10" written as day/month
    for m in re.finditer(r"\b(\d{1,2})[/.](\d{1,2})\b", text):
        found.append((m.start(), int(m.group(1)), int(m.group(2))))

    found.sort()
    seen: list[tuple[int, int]] = []
    for _, day, month in found:
        if 1 <= month <= 12 and 1 <= day <= 31 and (day, month) not in seen:
            seen.append((day, month))
    return seen


def _find_bare_range(text: str) -> tuple[int, int] | None:
    """'du 20 au 23 octobre' and '20-23 October': two days, one month."""
    patterns = [
        rf"du\s+(\d{{1,2}})\s+au\s+(\d{{1,2}})\s+(?:{MONTH_WORDS})",
        rf"from\s+(\d{{1,2}})(?:st|nd|rd|th)?\s+to\s+(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{MONTH_WORDS})",
        # The en dash here is not punctuation in our writing: it is a character a
        # traveller may type in a date range, so the rule has to accept it.
        rf"\b(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+(?:{MONTH_WORDS})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _weekday_on_or_after(today: date, weekday: int, next_week: bool) -> date:
    """The next occurrence of a weekday, or the one in the following week."""
    if next_week:
        monday_next = today + timedelta(days=7 - today.weekday())
        return monday_next + timedelta(days=weekday)
    ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=ahead or 7)


def _find_relative(text: str, today: date) -> date | None:
    """Dates a person gives by pointing rather than by naming.

    "next Friday", "demain", "\ub2e4\uc74c \uc8fc \uae08\uc694\uc77c" are all exact once you know
    today, so they are arithmetic, not a job for a language model.
    """
    for word in AFTER_TOMORROW_WORDS:
        if word in text:
            return today + timedelta(days=2)
    for word in TOMORROW_WORDS:
        if word in text:
            return today + timedelta(days=1)

    match = re.search(r"\b(?:in|dans)\s+(\d{1,2})\s+(days?|jours?|weeks?|semaines?)\b", text)
    if match:
        count = int(match.group(1))
        unit = match.group(2)
        return today + timedelta(days=count * (7 if unit.startswith(("week", "semaine")) else 1))

    next_week = any(word in text for word in NEXT_WEEK_WORDS)

    for name, weekday in sorted(WEEKDAYS.items(), key=lambda kv: -len(kv[0])):
        pattern = name if not name.isascii() else rf"\b{name}\b"
        if re.search(pattern, text):
            return _weekday_on_or_after(today, weekday, next_week)

    for word in WEEKEND_WORDS:
        if word in text:
            return _weekday_on_or_after(today, 5, next_week)

    if next_week:
        return today + timedelta(days=7 - today.weekday())

    return None


def read(message: str, today: date) -> DateReading:
    """Read what can be read with certainty. Everything else stays empty."""
    text = normalise(message)
    out = DateReading()

    # --- nights -------------------------------------------------------------
    nights_match = (
        re.search(r"(\d{1,2})\s*박", text)                    # 2박
        or re.search(r"(\d{1,2})\s*(?:nuits?|nights?)\b", text)
    )
    if nights_match:
        out.nights = int(nights_match.group(1))
        out.mark("nights", "rule")

    # --- dates --------------------------------------------------------------
    pairs = _find_day_month(text)
    bare_range = _find_bare_range(text)

    if bare_range and pairs:
        start_day, end_day = bare_range
        month = pairs[0][1]
        try:
            check_in = _resolve_year(month, start_day, today)
            check_out = _resolve_year(month, end_day, today)
            out.check_in = check_in
            out.mark("check_in", "rule")
            span = (check_out - check_in).days
            if span > 0 and out.nights is None:
                out.nights = span
                out.mark("nights", "rule")
        except ValueError:
            pass
    elif len(pairs) >= 2:
        first, second = pairs[0], pairs[1]
        check_in = _resolve_year(first[1], first[0], today)
        check_out = _resolve_year(second[1], second[0], today)
        out.check_in = check_in
        out.mark("check_in", "rule")
        span = (check_out - check_in).days
        if span > 0 and out.nights is None:
            out.nights = span
            out.mark("nights", "rule")
    elif len(pairs) == 1:
        day, month = pairs[0]
        out.check_in = _resolve_year(month, day, today)
        out.mark("check_in", "rule")
    else:
        relative = _find_relative(text, today)
        if relative is not None:
            out.check_in = relative
            out.mark("check_in", "rule")

    # --- guests -------------------------------------------------------------
    if re.search(r"혼자", text):  # 혼자, "alone"
        out.guests = 1
        out.mark("guests", "rule")
    else:
        guests_match = (
            re.search(r"(\d{1,2})\s*명", text)                # 2명
            or re.search(r"(\d{1,2})\s*인", text)             # 2인
            or re.search(r"(\d{1,2})\s*(?:personnes?|people|persons?|guests?|adultes?|pax)\b", text)
        )
        if guests_match:
            out.guests = int(guests_match.group(1))
            out.mark("guests", "rule")

    # --- breakfast ----------------------------------------------------------
    for word in BREAKFAST_WORDS:
        position = text.find(word)
        if position == -1:
            continue
        window = text[max(0, position - 20):position + len(word) + 10]
        out.breakfast = not any(neg in window for neg in NEGATIONS)
        out.mark("breakfast", "rule")
        break

    return out
