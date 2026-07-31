#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Explicit calendar date parsing shared by calendar_nlp.py and preview.py.

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

_MONTH = (r'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
          r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|'
          r'nov(?:ember)?|dec(?:ember)?')
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
