"""Parse the high-demand-window CSV uploaded by an admin.

Expected shape (header names are matched loosely, order does not matter)::

    start,end,label
    2026-09-07 09:00,2026-09-07 11:00,Monday morning peak
    2026-09-07 14:00,2026-09-07 16:30,Monday afternoon peak

``start``/``end`` are wall-clock times read in the study's timezone unless the
value carries its own UTC offset, or the file supplies a ``timezone`` column.
Bad rows are skipped with a warning rather than failing the whole upload, so
one typo in row 40 does not cost the other 39.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

START_KEYS = ('start', 'start_time', 'start_at', 'starts_at', 'begin', 'begins_at', 'from', 'start_datetime')
END_KEYS = ('end', 'end_time', 'end_at', 'ends_at', 'finish', 'until', 'to', 'end_datetime')
LABEL_KEYS = ('label', 'name', 'note', 'description', 'window', 'title')
TZ_KEYS = ('timezone', 'tz', 'time_zone')

# Tried in order.  ISO 8601 is handled separately first.
DATETIME_FORMATS = (
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M',
    '%Y/%m/%d %H:%M:%S',
    '%Y/%m/%d %H:%M',
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%Y %H:%M',
    '%m/%d/%y %H:%M',
    '%d-%m-%Y %H:%M',
    '%Y-%m-%d %I:%M %p',
    '%m/%d/%Y %I:%M %p',
    '%m/%d/%Y %I:%M%p',
)


@dataclass
class ParsedWindow:
    starts_at: int
    ends_at: int
    local_start: str
    local_end: str
    timezone: str
    label: Optional[str] = None
    row_number: int = 0


@dataclass
class ParseResult:
    windows: list[ParsedWindow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: int = 0


def _normalise_key(key: str) -> str:
    return (key or '').strip().lower().replace(' ', '_').replace('-', '_').lstrip('﻿')


def _pick(row: dict, keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        if key in row and (row[key] or '').strip():
            return row[key].strip()
    return None


def _resolve_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo('UTC')


def parse_datetime(value: str, tz: ZoneInfo) -> Optional[datetime]:
    """Parse one cell into an aware datetime, assuming *tz* when naive."""
    text = (value or '').strip()
    if not text:
        return None

    # A bare epoch second count.
    if text.isdigit() and len(text) >= 9:
        return datetime.fromtimestamp(int(text), tz=dt_timezone.utc)

    parsed: Optional[datetime] = None
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        for fmt in DATETIME_FORMATS:
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return None
    # A naive value is wall-clock time in the study's zone.
    return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed


def parse_demand_csv(content: str, default_timezone: str = 'America/New_York') -> ParseResult:
    """Turn CSV text into concrete windows, collecting per-row warnings."""
    result = ParseResult()

    text = content.lstrip('﻿')
    if not text.strip():
        result.warnings.append('The file is empty.')
        return result

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        result.warnings.append('No header row found. Expected at least "start" and "end" columns.')
        return result

    field_map = {_normalise_key(name): name for name in reader.fieldnames if name}
    if not any(k in field_map for k in START_KEYS) or not any(k in field_map for k in END_KEYS):
        result.warnings.append(
            'Could not find start/end columns. Found: '
            + ', '.join(sorted(field_map)) or '(none)'
        )
        return result

    default_zone = _resolve_zone(default_timezone)

    for index, raw_row in enumerate(reader, start=2):  # row 1 is the header
        row = {_normalise_key(k): (v if isinstance(v, str) else '') for k, v in raw_row.items() if k}
        if not any((v or '').strip() for v in row.values()):
            continue

        tz_name = _pick(row, TZ_KEYS) or default_timezone
        zone = _resolve_zone(tz_name)
        if tz_name != 'UTC' and zone.key == 'UTC' and tz_name.upper() != 'UTC':
            result.warnings.append(f'Row {index}: unknown timezone "{tz_name}", used UTC.')

        start_raw = _pick(row, START_KEYS)
        end_raw = _pick(row, END_KEYS)

        if not start_raw or not end_raw:
            result.skipped += 1
            result.warnings.append(f'Row {index}: missing a start or end value — skipped.')
            continue

        start_dt = parse_datetime(start_raw, zone)
        end_dt = parse_datetime(end_raw, zone)

        if start_dt is None:
            result.skipped += 1
            result.warnings.append(f'Row {index}: could not read start "{start_raw}" — skipped.')
            continue
        if end_dt is None:
            result.skipped += 1
            result.warnings.append(f'Row {index}: could not read end "{end_raw}" — skipped.')
            continue

        # "09:00,11:00" on the same day is the common case; an end that lands
        # before the start almost always means the window crosses midnight.
        if end_dt <= start_dt:
            if end_dt.date() == start_dt.date():
                end_dt = end_dt + timedelta(days=1)
                result.warnings.append(
                    f'Row {index}: end was at or before start — treated as crossing midnight.'
                )
            else:
                result.skipped += 1
                result.warnings.append(f'Row {index}: end "{end_raw}" is before start "{start_raw}" — skipped.')
                continue

        result.windows.append(
            ParsedWindow(
                starts_at=int(start_dt.timestamp()),
                ends_at=int(end_dt.timestamp()),
                local_start=start_dt.isoformat(),
                local_end=end_dt.isoformat(),
                timezone=zone.key or tz_name,
                label=_pick(row, LABEL_KEYS),
                row_number=index,
            )
        )

    if not result.windows and not result.warnings:
        result.warnings.append('No usable rows found.')

    # Overlaps are legal but usually a mistake worth surfacing.
    ordered = sorted(result.windows, key=lambda w: w.starts_at)
    for previous, current in zip(ordered, ordered[1:]):
        if current.starts_at < previous.ends_at:
            result.warnings.append(
                f'Rows {previous.row_number} and {current.row_number} overlap '
                f'({previous.local_start} → {previous.local_end} vs {current.local_start} → {current.local_end}).'
            )

    return result
