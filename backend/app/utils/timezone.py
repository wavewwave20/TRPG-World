from datetime import UTC, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def to_kst_iso(dt: datetime) -> str:
    """Convert a datetime to KST ISO8601 string (+09:00).

    - If dt is naive, treat it as UTC.
    - If dt is timezone-aware, convert to KST.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KST).isoformat()
