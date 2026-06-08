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


def date_to_compact(d: date) -> str:
    return d.strftime("%Y%m%d")
