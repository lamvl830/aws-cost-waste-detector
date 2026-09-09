from datetime import datetime, timezone

from aws_cost_waste_detector.lifecycle import (
    STATUS_OBSERVED,
    STATUS_OPEN,
    STATUS_RESOLVED,
    determine_status,
)


def test_new_finding_is_observed():
    first_seen = datetime(
        2026,
        9,
        8,
        12,
        0,
        tzinfo=timezone.utc,
    )

    now = datetime(
        2026,
        9,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    status = determine_status(
        first_seen=first_seen,
        currently_detected=True,
        grace_period_days=7,
        now=now,
    )

    assert status == STATUS_OBSERVED


def test_finding_becomes_open_after_grace_period():
    first_seen = datetime(
        2026,
        9,
        8,
        12,
        0,
        tzinfo=timezone.utc,
    )

    now = datetime(
        2026,
        9,
        15,
        12,
        0,
        tzinfo=timezone.utc,
    )

    status = determine_status(
        first_seen=first_seen,
        currently_detected=True,
        grace_period_days=7,
        now=now,
    )

    assert status == STATUS_OPEN


def test_missing_finding_becomes_resolved():
    first_seen = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    now = datetime(
        2026,
        9,
        15,
        12,
        0,
        tzinfo=timezone.utc,
    )

    status = determine_status(
        first_seen=first_seen,
        currently_detected=False,
        grace_period_days=7,
        now=now,
    )

    assert status == STATUS_RESOLVED