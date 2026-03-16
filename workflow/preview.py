#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List

# Add local lib dir so dateutil resolves to the bundled copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
try:
    from dateutil import parser as dateutil_parser
    _HAS_DATEUTIL = True
except ImportError:
    _HAS_DATEUTIL = False

def get_workflow_data_dir():
    """Get Alfred workflow data directory"""
    data_dir = os.getenv('alfred_workflow_data')
    if not data_dir:
        data_dir = os.path.expanduser('~/Library/Application Support/Alfred/Workflow Data/com.ariestwn.calendar.nlp')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

class EventPreview:
    def __init__(self):
        # Initialize patterns
        self.calendar_pattern = r'#(?:"([^"]+)"|\'([^\']+)\'|([^"\'\s]+))'
        self.time_pattern = r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b'
        self.location_pattern = r'(?:^|\s)(?:at|in)\s+([^,\.\d][^,\.]*?)(?=\s+(?:on|at|from|tomorrow|today|next|every|\d{1,2}(?::\d{2})?(?:am|pm)|url:|notes?:|link:)|\s*$)'
        
        # Load default calendar from config
        config_file = os.path.join(get_workflow_data_dir(), 'calendar_config.json')
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.default_calendar = config.get('default_calendar', 'Calendar')
        except:
            self.default_calendar = 'Calendar'
        
        # Weekday mapping for date parsing
        self.weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6
        }
        self.month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7,
            'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        self.date_range_pattern = r'from\s+(\w+\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*(?:-|to)\s*(\w+\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
        # Require am/pm for bare hours to avoid matching date numbers like "20" in "March 20"
        self.time_pattern = r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b|\b(\d{1,2})\s*(am|pm)\b'

    def get_calendar(self, text: str) -> str:
        """Extract calendar name from text or use default"""
        calendar_match = re.search(self.calendar_pattern, text)
        if calendar_match:
            # Only get the first non-None group
            requested_calendar = next((g for g in calendar_match.groups() if g is not None), None)
            if requested_calendar:
                # Print for debugging
                print(f"Debug - Calendar found in preview: {requested_calendar}", file=sys.stderr)
                return requested_calendar.strip()
        return self.default_calendar

    def parse_time(self, text: str) -> Optional[datetime]:
        """Parse time from text - requires am/pm for bare hours to avoid matching date numbers"""
        match = re.search(self.time_pattern, text, re.IGNORECASE)
        if match:
            if match.group(1) is not None:  # HH:MM format
                hour = int(match.group(1))
                minutes = int(match.group(2))
                meridiem = match.group(3).lower() if match.group(3) else ''
            else:  # bare number with required am/pm
                hour = int(match.group(4))
                minutes = 0
                meridiem = match.group(5).lower()

            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0

            now = datetime.now()
            return now.replace(hour=hour, minute=minutes, second=0, microsecond=0)
        return None

    def parse_duration(self, text: str) -> Optional[int]:
        """Extract duration in minutes from text. Returns None if no duration found."""
        # Time range like "3-5pm" or "3pm-5pm"
        range_match = re.search(
            r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            text, re.IGNORECASE
        )
        if range_match:
            sh, sm, smer, eh, em, emer = range_match.groups()
            sh, eh = int(sh), int(eh)
            sm, em = int(sm or 0), int(em or 0)
            # Propagate end meridiem to start when start has none
            if not smer and emer:
                smer = emer
            if smer and smer.lower() == 'pm' and sh != 12: sh += 12
            if emer and emer.lower() == 'pm' and eh != 12: eh += 12
            diff = (eh * 60 + em) - (sh * 60 + sm)
            if diff > 0:
                return diff

        # "for X hours" (including decimals like 1.5h)
        m = re.search(r'for\s+(\d+(?:\.\d+)?)\s*hours?', text, re.IGNORECASE)
        if m:
            return int(float(m.group(1)) * 60)

        # "for X minutes" / "for Xmin"
        m = re.search(r'for\s+(\d+)\s*min(?:ute)?s?', text, re.IGNORECASE)
        if m:
            return int(m.group(1))

        return None

    def parse_time_start(self, text: str) -> Optional[datetime]:
        """Like parse_time but returns the START of a time range (e.g. 3pm from 3-5pm)"""
        # Check for time range first — return start hour
        range_match = re.search(
            r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            text, re.IGNORECASE
        )
        if range_match:
            sh, sm, smer, _, _, emer = range_match.groups()
            sh = int(sh)
            sm = int(sm or 0)
            # Propagate end meridiem to start when start has none
            if not smer and emer:
                smer = emer
            if smer and smer.lower() == 'pm' and sh != 12: sh += 12
            elif smer and smer.lower() == 'am' and sh == 12: sh = 0
            now = datetime.now()
            return now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        return self.parse_time(text)

    def parse_explicit_date(self, text: str) -> Optional[datetime]:
        """Extract explicit month+day dates like 'March 20', '20 March', or '3/20'"""
        month_names = '|'.join(self.month_map.keys())
        # Try "Day Month" first to avoid mismatching time digits (e.g. "march 15" in "15:15")
        match = re.search(rf'\b(\d{{1,2}})\s+({month_names})\b', text, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            month = self.month_map[match.group(2).lower()]
        else:
            # Negative lookahead: exclude digits followed by ":" (part of HH:MM)
            match = re.search(rf'\b({month_names})\s+(\d{{1,2}})(?!:\d{{2}})\b', text, re.IGNORECASE)
            if match:
                month = self.month_map[match.group(1).lower()]
                day = int(match.group(2))
            else:
                return None
        today = datetime.now()
        try:
            result = datetime(today.year, month, day)
            if result.date() < today.date():
                result = datetime(today.year + 1, month, day)
            return result
        except ValueError:
            pass
        return None

    def get_next_weekday(self, weekday_name: str) -> datetime:
        """Get next occurrence of weekday"""
        weekday_name = weekday_name.lower()
        if weekday_name not in self.weekdays:
            return None
        
        today = datetime.now()
        target_weekday = self.weekdays[weekday_name]
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    def parse_date(self, text: str) -> str:
        """Parse and format date from text"""
        text_lower = text.lower()
        today = datetime.now()
        target_date = None
        target_time = self.parse_time_start(text)

        # Handle recurring events
        if 'every' in text_lower:
            for day in self.weekdays:
                if day in text_lower:
                    if target_time:
                        return f"Every {day.capitalize()} at {target_time.strftime('%-I:%M %p')}"
                    return f"Every {day.capitalize()}"

        # Handle date ranges
        range_match = re.search(self.date_range_pattern, text, re.IGNORECASE)
        if range_match:
            start_date = self.parse_explicit_date(range_match.group(1))
            end_date = self.parse_explicit_date(range_match.group(2))
            if start_date:
                end_label = end_date.strftime("%b %-d") if end_date else range_match.group(2)
                return f"{start_date.strftime('%A, %B %-d')} → {end_label}"

        # Handle relative dates
        if 'tomorrow' in text_lower:
            target_date = today + timedelta(days=1)
        elif 'next week' in text_lower:
            target_date = today + timedelta(days=7)

        # Handle explicit dates like "March 20", "24 March", "Tuesday 24 March".
        # This must run before bare weekday matching so "Tuesday 24 March" resolves
        # to March 24, not next Tuesday.
        if not target_date:
            target_date = self.parse_explicit_date(text)

        # Fall back to weekday-only matching (e.g., "meeting on Thursday")
        if not target_date:
            for day in self.weekdays:
                if day in text_lower:
                    target_date = self.get_next_weekday(day)
                    break

        if not target_date:
            target_date = today

        # Set time if specified
        if target_date and target_time:
            target_date = target_date.replace(
                hour=target_time.hour,
                minute=target_time.minute
            )

        # Build time string — always show end time (default 60 min if no duration specified)
        def time_range_str(start: datetime) -> str:
            if not target_time:
                return ""
            duration = self.parse_duration(text) or 60
            end = start + timedelta(minutes=duration)
            return f" at {start.strftime('%-I:%M %p')} – {end.strftime('%-I:%M %p')}"

        # Format output
        if target_date.date() == today.date():
            return f"Today{time_range_str(target_date)}"
        elif target_date.date() == (today + timedelta(days=1)).date():
            return f"Tomorrow{time_range_str(target_date)}"
        return target_date.strftime("%A, %B %-d") + time_range_str(target_date)

    def clean_title(self, text: str) -> str:
        """Clean title from input text"""
        # Remove calendar tag
        text = re.sub(self.calendar_pattern, '', text)

        patterns_to_remove = [
            # Recurrence
            r'\bevery\s+\w+',
            r'\bdaily\b|\bweekly\b|\bmonthly\b|\bannually\b|\byearly\b',
            # Weekdays
            r'\b(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?\b',
            # Relative dates
            r'\btomorrow\b|\btoday\b',
            r'\bnext\s+(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            # Explicit dates: "March 20", "20 March"
            r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?!:\d{2})\b',
            r'\b\d{1,2}(?!:\d{2})\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',
            # Time ranges like "3-5pm" — must come before bare time patterns
            r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*-\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)\b',
            # Time
            r'\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b',
            r'\b\d{1,2}:\d{2}\s*(?:am|pm)?\b',
            r'\b\d{1,2}\s*(?:am|pm)\b',
            # Duration (with or without space before unit)
            r'\bfor\s+\d+(?:\.\d+)?\s*(?:day|hour|hr|minute|min)s?\b',
            # Alerts
            r'\bwith\s+\d+\s*(?:minute|min|hour)s?\s+(?:alert|reminder)\b',
            r'\b(?:alert|remind)\s+\d+\s*(?:minute|min|hour)s?\s+before\b',
            # Prepositions
            r'\bfrom\b|\bto\b|\bon\b|\bat\b|\bin\b',
        ]

        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        return ' '.join(text.split())

    def parse_location(self, text: str) -> Optional[str]:
        """Extract location from text"""
        match = re.search(self.location_pattern, text)
        if match:
            location = match.group(1).strip()
            return location
        return None

    def expand_shorthands(self, text: str) -> str:
        """Expand common shorthand terms before parsing"""
        replacements = [
            (r'\btmrw\b|\btmr\b|\btmro\b', 'tomorrow'),
            (r'\btod\b|\btdy\b', 'today'),
            (r'\bnxt wk\b|\bnxt week\b|\bnw\b', 'next week'),
            (r'\bw/\b', 'with'),
            (r'\beve\b', 'evening'),
            (r'\bmtg\b|\bmeet\b', 'meeting'),
            (r'\bapt\b|\bappt\b', 'appointment'),
            (r'\bdr\b', 'doctor'),
            (r'\bwfh\b', 'work from home'),
            (r'\b(\d+)m\b(?!arch|ay)', 'for \\1 minutes'),
            (r'\b(\d+)h\b(?!our)', 'for \\1 hours'),
        ]
        result = text
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def generate_items(self, text: str) -> List[dict]:
        """Generate preview items"""
        text = self.expand_shorthands(text)
        title = self.clean_title(text)
        calendar = self.get_calendar(text)
        date = self.parse_date(text)
        location = self.parse_location(text)
        
        # Instead of removing the calendar tag, preserve it
        subtitle_parts = [f"📅 {calendar}"]
        if date:
            subtitle_parts.append(date)
        if location:
            subtitle_parts.append(f"📍 {location}")
        
        subtitle = " • ".join(subtitle_parts)
        
        return [{
            "title": title or "Type event details...",
            "subtitle": subtitle,
            "arg": text,  # Pass the original text with calendar tag
            "valid": bool(title and date != "Invalid date"),
            "icon": {"path": "icon.png"}
        }]

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "items": [{
                "title": "Type event details...",
                "subtitle": "Use natural language to describe your event",
                "valid": False,
                "icon": {"path": "icon.png"}
            }]
        }))
        return

    query = " ".join(sys.argv[1:])
    preview = EventPreview()
    items = preview.generate_items(query)
    print(json.dumps({"items": items}))

if __name__ == "__main__":
    main()