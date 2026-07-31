# Natural Language Calendar Alfred Workflow

An Alfred workflow that allows you to create calendar events using natural language.

## Features

- Create events using natural language
- Support for locations, alerts, notes, and URLs
- Recurring events support
- Multiple calendar support
- Date ranges and time specifications
- Smart parsing of event details

## Installation

1. Download the latest release from the releases page
2. Double click the `.alfredworkflow` file to install
3. Set up your default calendar using `clprofile`

## Usage

The workflow provides two commands:

### `cl` - Create Calendar Event

Examples:
```
cl meeting tomorrow at 2pm
cl lunch at Starbucks tomorrow 1pm
cl meeting tomorrow 2pm notes: Discuss project
cl zoom call tomorrow 3pm url: https://zoom.us/j/123
cl meeting tomorrow 2pm with 30min alert
cl team sync every monday at 10am
```

### `clprofile` - Set Default Calendar

## Basic Event Creation

> ❌ ← Means it's still not working as expected

```bash
# Simple event with time
cl meeting at 2pm
cl lunch at 12pm

# Short meridiem works too
cl call at 3p
cl standup at 9a

# Event for tomorrow
cl meeting tomorrow at 3pm
cl coffee break tomorrow 10:30am

# Event for specific day
cl meeting thursday at 2pm
```

## Specific Dates

```bash
# Month and day
cl meeting Oct 21 at 2pm
cl meeting October 21 at 2pm
cl party September 5th at 8pm

# Day and month
cl meeting 21 October at 2pm

# With an explicit year
cl conference December 3 2026 at 10am
cl meeting October 21, 2025 at 2pm

# Numeric formats
cl meeting 10/21 at 2pm      # month/day
cl deadline 21/10 at 5pm     # day/month when the first number can't be a month
cl flight 2026-11-02 at 6am
```

When the year is left out, the next occurrence of that date is used.

## Location Handling

```sh
# Event with simple location
cl lunch at Starbucks tomorrow 1pm

# Location with multiple words
cl meeting at Central Business District 3pm
cl dinner at The Coffee Bean & Tea Leaf 7pm

# Location with building/room
cl meeting at Conference Room A tomorrow 2pm
```

## Calendar Selection

```
# Using default calendar
cl meeting at 2pm

# Explicitly selecting calendar with #
cl #work meeting at 2pm
cl #personal dinner at 7pm
cl #family lunch tomorrow 1pm
```

## Duration Specification

```
# Specific duration in hours
cl meeting tomorrow 2pm for 2 hours
cl workshop at 10am for 3 hours

# Duration in minutes
cl call at 3pm for 30 minutes

# Time range format
cl meeting 2-3pm ❌
cl training 9:30am-11:30am ❌
```

## Reminders/Alert

```
# Minutes before
cl meeting tomorrow 2pm with 30min alert 
cl lunch at 1pm with 15min reminder

# Hours before
cl meeting at 3pm alert 1 hour before
cl call tomorrow 2pm with 2 hours reminder

# Multiple alerts
cl meeting tomorrow 3pm with 1 hour alert with 15min alert
```

## Notes And URL

```
# Adding notes
cl meeting tomorrow 2pm notes: Remember to bring laptop
cl lunch 1pm notes: Budget discussion

# Adding URLs (especially for virtual meetings)
cl zoom meeting 3pm url: https://zoom.us/j/123456
cl meeting 2pm url: https://meet.google.com/abc-def-ghi

# Combining notes and URLs
cl meeting 2pm url: https://zoom.us/j/123456 notes: Quarterly review
```

## Recurring Events

```sh
# Weekly recurring
cl team sync every monday at 10am
cl meeting every friday at 2pm

# Multiple days recurring
cl gym every monday and wednesday at 6pm ❌
cl class every tuesday and thursday at 3pm

# Daily recurring
cl standup every day at 9am

# Monthly recurring
cl team meeting every month at 2pm

# Yearly recurring
cl birthday every year on 5/16

# Recurring with end date
cl lunch every tuesday until 2/5 ❌
```

## Date Ranges

```sh
# Multi-day events
cl vacation from August 9-18 ❌
cl conference from 6/15 to 6/17 ❌

# Date range with times
cl training from 1/21 to 2/23 at 2pm ❌
```

## Complex Combination

```
# Location + Notes + Alert
cl haircut at Quick Cuts tomorrow 10am alert 30 minutes notes: Ask for John

# Recurring + Location + Calendar
cl #work team meeting at Conference Room A every monday 2pm

# Full featured event
cl #work project review at Room 301 tomorrow 2pm for 2 hours with 15min alert notes: Bring Q4 reports url: https://zoom.us/j/123456
```

## Relative Time

```
# Immediate events
cl quick meeting now

# Near future
cl meeting in 30 minutes
cl call in 2 hours
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.