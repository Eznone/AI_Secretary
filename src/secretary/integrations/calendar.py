"""Google Calendar tools registered with the AI tool registry."""

from datetime import datetime, timedelta, timezone

from secretary.agent.registry import tool
from secretary.auth.google import get_calendar_service


@tool
def list_calendar_events(date: str, max_results: int = 15) -> str:
    """List events from Google Calendar for a specific date.

    Args:
        date: ISO date string, e.g. '2026-05-25'. Pass today's date if the user didn't specify one.
        max_results: Maximum number of events to return. Default is 15.
    """
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
        lines.append(f"  {time_part}  {e.get('summary', '(no title)')}")
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
    service = get_calendar_service()
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": f"{date}T{start_time}:00", "timeZone": "UTC"},
        "end":   {"dateTime": f"{date}T{end_time}:00",   "timeZone": "UTC"},
    }
    result = service.events().insert(calendarId="primary", body=event).execute()
    link = result.get("htmlLink", "")
    return f"Event '{title}' created on {date} from {start_time} to {end_time}. Link: {link}"


@tool
def delete_calendar_event(event_id: str) -> str:
    """Delete an event from Google Calendar by its event ID.

    Args:
        event_id: The Google Calendar event ID (shown when listing events with include_ids=true).
    """
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return f"Event {event_id!r} deleted."


@tool
def list_calendar_events_with_ids(date: str) -> str:
    """List events for a date including their IDs (needed for deletion or editing).

    Args:
        date: ISO date string, e.g. '2026-05-25'.
    """
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
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = result.get("items", [])
    if not events:
        return f"No events found on {date}."

    lines = [f"Events on {date} (with IDs):"]
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        time_part = start[11:16] if "T" in start else start
        lines.append(f"  [{e['id']}] {time_part}  {e.get('summary', '(no title)')}")
    return "\n".join(lines)
