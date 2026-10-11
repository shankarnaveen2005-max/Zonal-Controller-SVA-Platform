"""Timezone formatting for web Digital Twin audit timestamps."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


_INDIA_TIME = ZoneInfo("Asia/Kolkata")


def format_audit_timestamp(event_time: str) -> str:
    """Render stored UTC audit timestamps in India Standard Time."""
    timestamp = datetime.fromisoformat(event_time)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(_INDIA_TIME).strftime(
        "%Y-%m-%d %I:%M:%S %p IST"
    )
