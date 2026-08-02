#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import date_parser

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
        self.meridiem = date_parser.MERIDIEM
        self.time_pattern = r'\b(\d{1,2})(?::(\d{2}))?\s*(' + self.meridiem + r')?\b'
        self.relative_time_pattern = r'in\s+(\d+)\s+(minutes?|hours?)'
        self.location_pattern = r'(?:^|\s)(?:at|in)\s+([^,\.\d][^,\.]*?)(?=\s+(?:on|at|from|tomorrow|today|next|every|\d{1,2}(?::\d{2})?(?:' + self.meridiem + r')|url:|notes?:|link:)|\s*$)'
        
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
        """Parse time from text"""
        now = datetime.now()

        # "in 30 minutes" / "in 2 hours" — matches how calendar_nlp reads it
        relative_match = re.search(self.relative_time_pattern, text, re.IGNORECASE)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2).lower()
            delta = timedelta(hours=amount) if 'hour' in unit else timedelta(minutes=amount)
            return (now + delta).replace(second=0, microsecond=0)

        # A range carries its own meridiem rules, so it has to win over the
        # single-time pattern, which would read "2-3pm" as plain "2".
        time_range = date_parser.find_time_range(text)
        if time_range:
            return now.replace(hour=time_range[0], minute=time_range[1],
                               second=0, microsecond=0)

        # A bare number is not necessarily an hour ("meeting 25 people"), so skip
        # values that cannot be a clock time instead of crashing the preview.
        for match in re.finditer(self.time_pattern, text, re.IGNORECASE):
            hour = date_parser.to_24h(int(match.group(1)), match.group(3))
            minutes = int(match.group(2)) if match.group(2) else 0

            if not 0 <= hour <= 23 or not 0 <= minutes <= 59:
                continue

            return now.replace(hour=hour, minute=minutes, second=0, microsecond=0)
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

    def strip_extras(self, text: str) -> str:
        """Drop URLs and the free-form notes section so digits inside them are
        never read as a date or a time"""
        text = re.sub(r'(?:url|link):\s*\S+', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'https?://\S+', ' ', text)
        text = re.sub(r'(?:notes?|description|details?):\s*.*$', ' ', text,
                      flags=re.IGNORECASE)
        return date_parser.strip_until(text)

    def without_date(self, text: str) -> str:
        """Text with any explicit date removed, so it cannot leak into the
        title or the location"""
        explicit_date = date_parser.find_date(self.strip_extras(text))
        if explicit_date:
            text = date_parser.strip_date(text, explicit_date[1])
        return text

    def find_weekday(self, text: str) -> Optional[str]:
        """Find a weekday mentioned in text, without matching inside other
        words ("satellite" must not count as "sat")"""
        for day in self.weekdays:
            if re.search(r'\b' + day + r's?\b', text):
                return day
        return None

    def parse_date(self, text: str) -> str:
        """Parse and format date from text"""
        text_lower = self.strip_extras(text.lower())
        today = datetime.now()
        target_date = None

        # A range is shown whole. Its text is removed first, otherwise the day
        # number of the second date is read as the time.
        date_range = date_parser.find_date_range(text_lower)
        if date_range:
            start, end, range_str = date_range
            rest = date_parser.strip_date(text_lower, range_str)
            at_time = self.parse_time(rest)
            span = f"{start.strftime('%B %-d')} – {end.strftime('%B %-d')}"
            return f"{span} at {at_time.strftime('%-I:%M %p')}" if at_time else span

        # An explicit date wins over everything else, and has to be removed
        # before the time is parsed so "Oct 21" is not read as 21:00.
        explicit_date = date_parser.find_date(text_lower)
        if explicit_date:
            target_date, date_str = explicit_date
            text_lower = date_parser.strip_date(text_lower, date_str)

        target_time = self.parse_time(text_lower)

        # Handle recurring events
        if 'every' in text_lower:
            day = self.find_weekday(text_lower)
            if day:
                if target_time:
                    return f"Every {day.capitalize()} at {target_time.strftime('%-I:%M %p')}"
                return f"Every {day.capitalize()}"

        # Handle relative dates
        if not target_date:
            if 'tomorrow' in text_lower:
                target_date = today + timedelta(days=1)
            elif 'next week' in text_lower:
                target_date = today + timedelta(days=7)

        # Handle weekdays
        if not target_date:
            day = self.find_weekday(text_lower)
            if day:
                target_date = self.get_next_weekday(day)

        if not target_date:
            target_date = today

        # Set time if specified
        if target_date and target_time:
            target_date = target_date.replace(
                hour=target_time.hour,
                minute=target_time.minute
            )

        # Format output
        if not target_date:
            return "Invalid date"
        
        if target_date.date() == today.date():
            return f"Today at {target_date.strftime('%-I:%M %p')}"
        elif target_date.date() == (today + timedelta(days=1)).date():
            return f"Tomorrow at {target_date.strftime('%-I:%M %p')}"
        return target_date.strftime("%A, %B %-d at %-I:%M %p")

    def clean_title(self, text: str) -> str:
        """Clean title from input text"""
        # Remove calendar tag
        text = re.sub(self.calendar_pattern, '', text)

        # Remove an explicit date so "meeting Oct 21" is titled "meeting"
        text = self.without_date(text)

        # Drop the location phrase itself rather than every "in <word>", which
        # would eat the "in" out of "check in with Bob"
        match = re.search(self.location_pattern, text)
        if match and date_parser.is_place_phrase(match.group(1).strip()):
            text = text.replace(match.group(0), ' ', 1)

        # Same list the created event uses, so the two titles cannot drift
        patterns_to_remove = date_parser.title_noise_patterns(self.meridiem)
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return ' '.join(text.split())

    def parse_location(self, text: str) -> Optional[str]:
        """Extract location from text"""
        match = re.search(self.location_pattern, text)
        if match:
            location = match.group(1).strip()
            if not date_parser.is_place_phrase(location):
                return None
            return location
        return None

    def generate_items(self, text: str) -> List[dict]:
        """Generate preview items"""
        title = self.clean_title(text)
        calendar = self.get_calendar(text)
        date = self.parse_date(text)
        location = self.parse_location(self.without_date(text))
        
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