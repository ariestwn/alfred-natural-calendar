# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alfred workflow for creating macOS Calendar events via natural language input. Users type `cl <natural language>` in Alfred to parse and create calendar events using AppleScript.

## Build & Run

```bash
# Build distributable .alfredworkflow package
python scripts/build.py
# Output: dist/Natural-Calendar-[VERSION].alfredworkflow

# Install dependencies (normally auto-runs on first use)
python workflow/setup.py
# Installs python-dateutil into workflow/lib/
```

There are no tests, linter, or formatter configured.

## Architecture

Three main entry points, all invoked by Alfred as separate processes:

1. **`workflow/preview.py`** — Script filter. Parses input in real-time and returns Alfred JSON items for live preview (title, date, location, calendar).
2. **`workflow/calendar_nlp.py`** — Script action. Full parse of input, generates and executes AppleScript via `osascript` to create the calendar event. Contains `CalendarNLPProcessor` with all NLP parsing logic.
3. **`workflow/calendar_profile.py`** — Manages calendar selection. Queries macOS Calendar for writable calendars via AppleScript, stores default in config JSON.

**Execution flow:** Alfred input → `preview.py` (live feedback) → user confirms → `calendar_nlp.py` (creates event) → notification.

## Key Design Details

- **NLP parsing** in `CalendarNLPProcessor` uses regex patterns + `python-dateutil` fuzzy parsing. Parsing order matters: calendar (#name) → recurrence → alerts → duration → location → URL → notes → date/time → title (remainder).
- **Calendar selection:** `#CalendarName` syntax or `#"Calendar Name"` for names with spaces. Default calendar stored in `~/Library/Application Support/Alfred/Workflow Data/com.ariestwn.calendar.nlp/calendar_config.json`.
- **Dependencies** are installed to `workflow/lib/` (gitignored) and added to `sys.path` at runtime.
- **Bundle ID:** `com.ariestwn.calendar.nlp`
- **Alfred keywords:** `cl` (create event), `clprofile` (select calendar)

## Known Limitations (from README)

Time ranges (`2-3pm`), multiple recurring days, monthly/yearly with specific dates, date ranges (`August 9-18`), and relative time (`in 30 minutes`) are not fully working.
