#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Date and time expression parsing shared by calendar_nlp.py and preview.py.

Anything both entry points need to agree on belongs here. They used to keep
private copies of these patterns, which is how the preview ended up showing a
different time from the event it created.

Deliberately stdlib-only: preview.py runs on every keystroke and must not pay
for the bundled lib/ dependencies.
"""

import re
from datetime import datetime
from typing import Optional, Tuple

# Keyed by the first three letters of a month name, which are unique.
MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

# Public: callers that need to spot a month name in their own patterns, such as
# the "from August 9-18" date range, build on this.
MONTH_PATTERN = (r'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
                 r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|'
                 r'nov(?:ember)?|dec(?:ember)?')
_MONTH = MONTH_PATTERN
_ORD = r'(?:st|nd|rd|th)?'

# A day number is always required, so bare month mentions ("meeting in March")
# are never mistaken for a date.
_PATTERNS = [
    # 2025-10-21
    ('iso', re.compile(r'\b(?:on\s+)?(\d{4})-(\d{1,2})-(\d{1,2})\b')),
    # Oct 21 / October 21st, 2025 / Dec 3 2026
    ('month_day', re.compile(
        r'\b(?:on\s+)?(' + _MONTH + r')\.?\s+(\d{1,2})' + _ORD +
        r'(?:\s*,?\s*(\d{4}))?\b', re.IGNORECASE)),
    # 21 October / 21st October 2025
    ('day_month', re.compile(
        r'\b(?:on\s+)?(\d{1,2})' + _ORD + r'\s+(' + _MONTH + r')\.?'
        r'(?:\s*,?\s*(\d{4}))?\b', re.IGNORECASE)),
    # 10/21 / 10/21/25 / 21/10/2025
    ('numeric', re.compile(r'\b(?:on\s+)?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b')),
]


def _normalize_year(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    year = int(raw)
    return 2000 + year if year < 100 else year


def _build(year: Optional[int], month: int, day: int,
           reference: datetime) -> Optional[datetime]:
    """Build a datetime, rolling to next year when no year was given and the
    date has already passed. Keeps the reference time-of-day so a date without
    a time behaves like "tomorrow" does."""
    explicit_year = year is not None
    if not explicit_year:
        year = reference.year

    try:
        result = datetime(year, month, day, reference.hour, reference.minute)
    except ValueError:
        return None

    if not explicit_year and result.date() < reference.date():
        try:
            result = result.replace(year=year + 1)
        except ValueError:  # Feb 29 on a non-leap year
            return None

    return result


def _from_match(kind: str, match, reference: datetime) -> Optional[datetime]:
    if kind == 'iso':
        year, month, day = match.groups()
        return _build(int(year), int(month), int(day), reference)

    if kind == 'month_day':
        month_name, day, year = match.groups()
        return _build(_normalize_year(year), MONTHS[month_name[:3].lower()],
                      int(day), reference)

    if kind == 'day_month':
        day, month_name, year = match.groups()
        return _build(_normalize_year(year), MONTHS[month_name[:3].lower()],
                      int(day), reference)

    # numeric: month/day by default, day/month when the first number can only
    # be a day (e.g. "21/10").
    first, second, year = match.groups()
    first, second = int(first), int(second)
    if first > 12 and second <= 12:
        month, day = second, first
    else:
        month, day = first, second
    return _build(_normalize_year(year), month, day, reference)


# "every tuesday until 2/5" ends a recurrence, it does not start the event.
_END_DATE_PREFIX = re.compile(
    r'\b(?:until|untill|till|til|thru|through|ends?|ending)\s+(?:on\s+)?$',
    re.IGNORECASE)


def find_date(text: str,
              reference: Optional[datetime] = None
              ) -> Optional[Tuple[datetime, str]]:
    """Find an explicit calendar date in text.

    Returns (date, matched_text) or None. The matched text is returned so the
    caller can strip it before parsing a time — otherwise the day number in
    "Oct 21" is read as 21:00.
    """
    reference = reference or datetime.now()

    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            if _END_DATE_PREFIX.search(text[:match.start()]):
                continue
            parsed = _from_match(kind, match, reference)
            if parsed:
                return parsed, match.group(0)
    return None


def strip_date(text: str, matched: str) -> str:
    """Remove a matched date expression from text."""
    return re.sub(r'\s+', ' ', text.replace(matched, ' ', 1)).strip()


# Longest first, so "3pm" is not read as "3p" followed by a stray "m"
MERIDIEM = r'am|pm|a|p'

# The end must carry a meridiem; a bare "2-3" is too ambiguous to treat as a
# time range at all.
TIME_RANGE_PATTERN = (r'\b(\d{1,2})(?::(\d{2}))?\s*(' + MERIDIEM + r')?'
                      r'\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(' + MERIDIEM + r')\b')

# Public: the title cleanup strips this clause too.
UNTIL_PATTERN = r'\buntil\b.*$'


def to_24h(hour: int, meridiem: Optional[str]) -> int:
    """Hour in 24-hour form. "pm"/"p" mean afternoon, "am"/"a" morning."""
    marker = meridiem.lower()[:1] if meridiem else ''
    if marker == 'p' and hour != 12:
        return hour + 12
    if marker == 'a' and hour == 12:
        return 0
    return hour


def find_time_range(text: str) -> Optional[Tuple[int, int, int, int]]:
    """Start and end of a range like "2-3pm" as (hour, minute, hour, minute).

    A range usually marks the meridiem once, at the end, so "2-3pm" has to read
    as 14:00-15:00 rather than 02:00-03:00.
    """
    match = re.search(TIME_RANGE_PATTERN, text, re.IGNORECASE)
    if not match:
        return None

    start_h, start_m, start_mer, end_h, end_m, end_mer = match.groups()
    start_m = int(start_m) if start_m else 0
    end_m = int(end_m) if end_m else 0
    start = to_24h(int(start_h), start_mer or end_mer)
    end = to_24h(int(end_h), end_mer)

    # An inherited meridiem that puts the start after the end is wrong:
    # "11-1pm" is 11:00 to 13:00, not 23:00 to 13:00.
    if not start_mer and start * 60 + start_m > end * 60 + end_m:
        start = int(start_h)

    if not (0 <= start <= 23 and 0 <= end <= 23):
        return None

    return start, start_m, end, end_m


def strip_until(text: str) -> str:
    """Drop an "until <date>" clause.

    That date ends a recurrence, so it must not be read as the event's own date
    or time.
    """
    return re.sub(UNTIL_PATTERN, '', text, flags=re.IGNORECASE)


def find_date_range(text: str) -> Optional[Tuple[datetime, datetime, str]]:
    """Parse a date range, returning (start, end, matched_text).

    Both dates come back at midnight; the caller applies any explicit
    time-of-day. The matched text is returned so the caller can strip it
    before reading a time out of what is left.
    """
    # "from August 9-18" — the second day inherits the month
    same_month = re.search(
        r'from\s+(' + MONTH_PATTERN + r')\.?\s+(\d{1,2})'
        r'\s*(?:-|to|until|through)\s*(\d{1,2})\b', text, re.IGNORECASE)
    if same_month:
        month_name, first, second = same_month.groups()
        start = find_date(f'{month_name} {first}')
        end = find_date(f'{month_name} {second}')
        if start and end:
            return _order_range(start[0], end[0], same_month.group(0))

    # "from <date> to <date>"
    both = re.search(r'from\s+(.+?)\s*(?:-|\bto\b|\buntil\b|\bthrough\b)\s+(.+)$',
                     text, re.IGNORECASE)
    if both:
        start = find_date(both.group(1))
        end = find_date(both.group(2))
        if start and end:
            # Trim the trailing time off the matched span so "at 2pm" stays
            # available to the caller
            matched = both.group(0)
            tail = re.search(r'\s+at\s+\d', matched)
            if tail:
                matched = matched[:tail.start()]
            return _order_range(start[0], end[0], matched)

    return None

def _order_range(start: datetime, end: datetime,
             matched: str) -> Tuple[datetime, datetime, str]:
    """Normalize a range to midnight, pushing the end past the start"""
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=0, minute=0, second=0, microsecond=0)
    if end < start:
        end = end.replace(year=end.year + 1)
    return start, end, matched
