import pytest

from aws_cost_waste_detector.notifications import should_notify


@pytest.mark.parametrize(
    ("priority_label", "expected"),
    [
        ("LOW", False),
        ("MEDIUM", False),
        ("HIGH", True),
        ("CRITICAL", True),
        ("high", True),
        (" critical ", True),
    ],
)
def test_should_notify(
    priority_label: str,
    expected: bool,
):
    assert (
        should_notify(
            priority_label=priority_label,
        )
        is expected
    )


from aws_cost_waste_detector.notifications import (
    notification_timestamp,
    should_notify,
    should_send_finding_notification,
)


def test_high_priority_finding_without_previous_alert_should_send():
    item = {
        "priority_label": "HIGH",
        "last_notified_at": None,
    }

    assert should_send_finding_notification(item) is True


def test_critical_finding_without_previous_alert_should_send():
    item = {
        "priority_label": "CRITICAL",
    }

    assert should_send_finding_notification(item) is True


def test_low_priority_finding_should_not_send():
    item = {
        "priority_label": "LOW",
        "last_notified_at": None,
    }

    assert should_send_finding_notification(item) is False


def test_previously_notified_finding_should_not_send_again():
    item = {
        "priority_label": "HIGH",
        "last_notified_at": "2026-09-10T12:00:00+00:00",
    }

    assert should_send_finding_notification(item) is False


def test_notification_timestamp_is_utc():
    timestamp = notification_timestamp()

    assert timestamp.endswith("+00:00")