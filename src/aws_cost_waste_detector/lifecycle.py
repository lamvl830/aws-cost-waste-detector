from datetime import datetime, timedelta, timezone


STATUS_OBSERVED = "OBSERVED"
STATUS_OPEN = "OPEN"
STATUS_RESOLVED = "RESOLVED"


def determine_status(
    *,
    first_seen: datetime,
    currently_detected: bool,
    grace_period_days: int = 7,
    now: datetime | None = None,
) -> str:
    """
    Determine the lifecycle status of a cost-waste finding.

    Lifecycle:

    OBSERVED
        A finding has been detected but has not existed long enough
        to be considered actionable waste.

    OPEN
        The finding has remained continuously detected for at least
        the configured grace period.

    RESOLVED
        A previously stored finding is no longer detected by the scanner.
    """

    # Allow tests to provide a fixed timestamp while production code
    # defaults to the current UTC time.
    if now is None:
        now = datetime.now(timezone.utc)

    # A stored finding that disappears from the current scan is resolved.
    if not currently_detected:
        return STATUS_RESOLVED

    grace_period = timedelta(days=grace_period_days)

    # Findings remain OBSERVED until they have survived the full grace period.
    if now - first_seen < grace_period:
        return STATUS_OBSERVED

    return STATUS_OPEN