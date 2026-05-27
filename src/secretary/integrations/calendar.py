"""Google Calendar tools registered with the AI tool registry."""

import re
from datetime import datetime, timedelta, timezone

from secretary.agent.registry import tool
from secretary.auth.google import get_calendar_service
from secretary.platform_dirs import get_local_timezone

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _validate_date(value: str) -> str | None:
    """Return an error string if value is not a valid YYYY-MM-DD date, else None."""
    if not _DATE_RE.match(value):
        return f"Invalid date {value!r} — expected YYYY-MM-DD format."
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return f"Invalid date {value!r} — not a real calendar date."
    return None


def _validate_time(value: str, label: str) -> str | None:
    """Return an error string if value is not a valid HH:MM time, else None."""
    if not _TIME_RE.match(value):
        return f"Invalid {label} {value!r} — expected HH:MM 24-hour format."
    h, m = map(int, value.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return f"Invalid {label} {value!r} — hours must be 0-23, minutes 0-59."
    return None


@tool
def list_calendar_events(date: str, max_results: int = 15) -> str:
    """List events from Google Calendar for a specific date, including their IDs.

    Always includes event IDs so the model can reference them for deletion or editing.

    Args:
        date: ISO date string, e.g. '2026-05-25'. Pass today's date if the user didn't specify one.
        max_results: Maximum number of events to return. Default is 15.
    """
    if err := _validate_date(date):
        return err
    local_tz = get_local_timezone()
    service = get_calendar_service()
    day_start = datetime.fromisoformat(date).replace(
        hour=0, minute=0, second=0, tzinfo=timezone.utc
    )
    day_end = day_start + timedelta(days=1)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = result.get("items", [])
    if not events:
        return f"No events found on {date}."

    lines = [f"Events on {date}:"]
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        # Strip timezone offset for cleaner display
        time_part = start[11:16] if "T" in start else start
        lines.append(f"  [{e['id']}] {time_part}  {e.get('summary', '(no title)')}")
    return "\n".join(lines)


@tool
def create_calendar_event(
    title: str,
    date: str,
    start_time: str,
    end_time: str,
    description: str = "",
) -> str:
    """Create a new event in the user's primary Google Calendar.

    Args:
        title: The event title/summary.
        date: ISO date string, e.g. '2026-05-26'.
        start_time: Start time in HH:MM 24-hour format, e.g. '14:00'.
        end_time: End time in HH:MM 24-hour format, e.g. '15:00'.
        description: Optional event description or notes.
    """
    for err in (
        _validate_date(date),
        _validate_time(start_time, "start_time"),
        _validate_time(end_time, "end_time"),
    ):
        if err:
            return err
    local_tz = get_local_timezone()
    service = get_calendar_service()
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": f"{date}T{start_time}:00", "timeZone": local_tz},
        "end":   {"dateTime": f"{date}T{end_time}:00",   "timeZone": local_tz},
    }
    result = service.events().insert(calendarId="primary", body=event).execute()
    link = result.get("htmlLink", "")
    return f"Event '{title}' created on {date} from {start_time} to {end_time}. Link: {link}"


@tool
def delete_calendar_event(event_id: str) -> str:
    """Delete an event from Google Calendar by its event ID.

    Args:
        event_id: The Google Calendar event ID (shown in list_calendar_events output).
    """
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return f"Event {event_id!r} deleted."

