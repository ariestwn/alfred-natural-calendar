#!/Users/anaderi/micromamba/envs/obsidian/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List

def ensure_dependencies():
    """Ensure all required dependencies are installed"""
    workflow_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(workflow_dir, 'lib')

    if not os.path.exists(lib_dir) or not os.path.exists(os.path.join(lib_dir, 'dateutil')):
        setup_script = os.path.join(workflow_dir, 'setup.py')
        try:
            subprocess.run([sys.executable, setup_script],
                         check=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print(json.dumps({
                "items": [{
                    "title": "Setup failed",
                    "subtitle": "Please check the workflow logs.",
                    "valid": False
                }]
            }))
            sys.exit(1)

ensure_dependencies()

# Use only the local lib directory for dateutil
lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
sys.path.insert(0, lib_dir)
from dateutil import parser as dateutil_parser

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
        """Parse time from text, preferring matches with am/pm over bare numbers"""
        matches = list(re.finditer(self.time_pattern, text, re.IGNORECASE))

        # Prefer matches with am/pm marker
        match = None
        for m in matches:
            if m.group(3):  # has am/pm
                match = m
                break
        if not match and matches:
            # Fall back to colon-formatted (e.g. "14:30") or valid bare hours
            for m in matches:
                if m.group(2) or int(m.group(1)) <= 23:
                    match = m
                    break

        if match:
            hour = int(match.group(1))
            minutes = int(match.group(2)) if match.group(2) else 0
            meridiem = match.group(3).lower() if match.group(3) else ''

            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0

            now = datetime.now()
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

    def parse_date(self, text: str) -> str:
        """Parse and format date from text"""
        # Strip URLs before parsing (numbers in URLs confuse dateutil)
        text = re.sub(r'https?://\S+', '', text)
        text_lower = text.lower()
        today = datetime.now()
        target_date = None
        target_time = self.parse_time(text_lower)

        # Handle recurring events
        if 'every' in text_lower:
            for day in self.weekdays:
                if day in text_lower:
                    if target_time:
                        return f"Every {day.capitalize()} at {target_time.strftime('%-I:%M %p')}"
                    return f"Every {day.capitalize()}"

        # Handle relative dates first
        if 'tomorrow' in text_lower:
            target_date = today + timedelta(days=1)
        elif 'next week' in text_lower:
            target_date = today + timedelta(days=7)
        else:
            # Try dateutil fuzzy parsing — handles absolute dates like "March 24",
            # "Tuesday 24 March", "June 5", etc.
            try:
                parsed = dateutil_parser.parse(text, fuzzy=True,
                    default=today.replace(hour=0, minute=0, second=0, microsecond=0))
                if parsed.date() != today.date():
                    target_date = parsed
                    if target_date.date() < today.date():
                        target_date = target_date.replace(year=target_date.year + 1)
            except (ValueError, OverflowError):
                pass

            # Fall back to weekday-only matching if no absolute date found
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
        # Strip URLs
        text = re.sub(r'https?://\S+', '', text)

        # Remove date/time patterns
        patterns_to_remove = [
            r'\b(?:tomorrow|today|next|on|at|from|to|every|daily|weekly|monthly)\b.*$',
            r'\d{1,2}(?::(\d{2}))?\s*(?:am|pm).*$',
            r'for\s+\d+\s+(?:day|hour|minute|min)s?.*$',
            r'(?:alert|remind).*$',
            r'with\s+\d+\s*(?:minute|min|hour)s?\s+(?:alert|reminder)',
            r'(?:^|\s)(?:at|in)\s+([^,\.\d][^,\.]*?)(?=\s+|$)'
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

    def generate_items(self, text: str) -> List[dict]:
        """Generate preview items"""
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
