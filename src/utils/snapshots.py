from datetime import date, datetime, timedelta, timezone


def get_snapshot_metadata() -> tuple[datetime, date]:
    """Return (snapshot_at UTC now, snapshot_date yesterday).

    Every ingestion task calls this once to stamp all rows consistently.
    snapshot_date represents the 24-hour window the API data covers,
    which is always the day prior to the run.
    """
    snapshot_at = datetime.now(timezone.utc)
    snapshot_date = (snapshot_at - timedelta(days=1)).date()
    return snapshot_at, snapshot_date


def build_snapshot_columns(
    snapshot_at: datetime,
    snapshot_date: date,
) -> dict[str, str]:
    """Return snapshot timestamp columns as ISO strings ready for serialisation."""
    return {
        "snapshot_at": snapshot_at.isoformat(),
        "snapshot_date": snapshot_date.isoformat(),
    }
