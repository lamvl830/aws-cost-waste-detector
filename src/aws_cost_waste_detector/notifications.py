from datetime import datetime, timezone
from typing import Any


ALERT_PRIORITY_LABELS = {
    "HIGH",
    "CRITICAL",
}


def should_notify (
    *,
    priority_label: str,
) -> bool: 
    """
    Decide whether finding should trigger notification

    Only HIGH and CRITICAL priority findings  trigger notifications.
    """
    normalized_label = priority_label.strip().upper()

    return normalized_label in ALERT_PRIORITY_LABELS


def should_send_finding_notification(
    item: dict[str, Any]
) -> bool:
    """
    Decide whether a finding should trigger notification

    Finding eligible if it has never been notified and has a priority label of HIGH or CRITICAL.
    """
    if not should_notify(priority_label=item.get("priority_label", "")):
        return False

    return item.get("last_notified_at") is None


def notification_timestamp() -> str:
    """
    Return current UTC timestamp used when recording alert
    """
    return datetime.now(timezone.utc).isoformat()