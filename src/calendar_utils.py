"""Utility helpers for the Calendario features (ICS export, formatting)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Dict

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _escape_ics(value: str) -> str:
    """Escape commas, semicolons, and newlines for ICS fields."""
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _format_dt(dt_str: str) -> str:
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%Y%m%dT%H%M%S")


def _format_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def events_to_ics(events: Iterable[Dict], calendar_name: str = "Agenda Libro Soci") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LibroSoci//Calendario//IT",
        f"X-WR-CALNAME:{_escape_ics(calendar_name)}",
    ]
    for ev in events:
        dtstart = _format_dt(ev["start_ts"])
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:librosoci-event-{ev['id']}@ari",
                f"DTSTAMP:{_format_stamp()}",
                f"DTSTART:{dtstart}",
                f"SUMMARY:{_escape_ics(ev.get('titolo', 'Evento'))}",
                f"CATEGORIES:{_escape_ics(ev.get('tipo', 'Altro'))}",
            ]
        )
        if ev.get("luogo"):
            lines.append(f"LOCATION:{_escape_ics(ev['luogo'])}")
        descr_parts = []
        if ev.get("descrizione"):
            descr_parts.append(ev["descrizione"])
        if ev.get("origin"):
            descr_parts.append(f"Origine: {ev['origin']}")
        if descr_parts:
            lines.append(f"DESCRIPTION:{_escape_ics('\n'.join(descr_parts))}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"