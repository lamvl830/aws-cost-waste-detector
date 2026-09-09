import pytest

from aws_cost_waste_detector.prioritization import (
    calculate_age_days,
    calculate_current_finding_priority,
    calculate_finding_priority,
    calculate_priority_score,
    priority_label,
)
from decimal import Decimal
from aws_cost_waste_detector.models import Finding


def test_calculate_priority_score():
    score = calculate_priority_score(
        estimated_monthly_savings=40.0,
        age_days=30,
        severity="LOW",
    )

    # 40 savings + 25 age + 0 severity
    assert score == 65


def test_priority_score_caps_savings_at_60():
    score = calculate_priority_score(
        estimated_monthly_savings=500.0,
        age_days=0,
        severity="LOW",
    )

    assert score == 60


def test_priority_score_caps_age_at_25():
    score = calculate_priority_score(
        estimated_monthly_savings=0.0,
        age_days=100,
        severity="LOW",
    )

    assert score == 25


def test_priority_score_adds_severity_points():
    score = calculate_priority_score(
        estimated_monthly_savings=10.0,
        age_days=10,
        severity="HIGH",
    )

    # 10 savings + 10 age + 10 severity
    assert score == 30


def test_priority_score_handles_missing_savings():
    score = calculate_priority_score(
        estimated_monthly_savings=None,
        age_days=10,
        severity="MEDIUM",
    )

    assert score == 15


def test_priority_score_rejects_negative_age():
    with pytest.raises(
        ValueError,
        match="age_days cannot be negative",
    ):
        calculate_priority_score(
            estimated_monthly_savings=10.0,
            age_days=-1,
            severity="LOW",
        )


def test_priority_score_rejects_unknown_severity():
    with pytest.raises(
        ValueError,
        match="Unsupported severity",
    ):
        calculate_priority_score(
            estimated_monthly_savings=10.0,
            age_days=1,
            severity="UNKNOWN",
        )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "LOW"),
        (29, "LOW"),
        (30, "MEDIUM"),
        (59, "MEDIUM"),
        (60, "HIGH"),
        (79, "HIGH"),
        (80, "CRITICAL"),
        (100, "CRITICAL"),
    ],
)
def test_priority_labels(
    score: int,
    expected: str,
):
    assert priority_label(score) == expected

from datetime import datetime, timezone


def test_calculate_age_days():
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
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    age_days = calculate_age_days(
        first_seen=first_seen.isoformat(),
        now=now,
    )

    assert age_days == 9


def test_calculate_age_days_uses_whole_days():
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
        2,
        11,
        59,
        tzinfo=timezone.utc,
    )

    age_days = calculate_age_days(
        first_seen=first_seen.isoformat(),
        now=now,
    )

    assert age_days == 0


def test_calculate_age_days_rejects_future_timestamp():
    first_seen = datetime(
        2026,
        9,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    now = datetime(
        2026,
        9,
        9,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with pytest.raises(
        ValueError,
        match="first_seen cannot be in the future",
    ):
        calculate_age_days(
            first_seen=first_seen.isoformat(),
            now=now,
        )


def test_calculate_finding_priority():
    now = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=timezone.utc,
    )

    item = {
        "first_seen": "2026-09-01T12:00:00+00:00",
        "estimated_monthly_savings": 40.0,
        "severity": "LOW",
    }

    result = calculate_finding_priority(
        item,
        now=now,
    )

    assert result == {
        "age_days": 10,
        "priority_score": 50,
        "priority_label": "MEDIUM",
    }


def test_calculate_finding_priority_handles_dynamodb_decimal():
    now = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=timezone.utc,
    )

    item = {
        "first_seen": "2026-09-01T12:00:00+00:00",
        "estimated_monthly_savings": Decimal("100.00"),
        "severity": "HIGH",
    }

    result = calculate_finding_priority(
        item,
        now=now,
    )

    # 60 capped savings + 10 age + 10 severity
    assert result["priority_score"] == 80
    assert result["priority_label"] == "CRITICAL"


def test_calculate_finding_priority_handles_missing_savings():
    now = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=timezone.utc,
    )

    item = {
        "first_seen": "2026-09-01T12:00:00+00:00",
        "estimated_monthly_savings": None,
        "severity": "MEDIUM",
    }

    result = calculate_finding_priority(
        item,
        now=now,
    )

    assert result["age_days"] == 10
    assert result["priority_score"] == 15
    assert result["priority_label"] == "LOW"


def test_calculate_current_finding_priority_for_new_finding():
    finding = Finding(
        rule_id="EBS_CURRENTLY_UNATTACHED",
        account_id="123456789012",
        region="us-east-1",
        resource_arn=(
            "arn:aws:ec2:us-east-1:123456789012:"
            "volume/vol-123"
        ),
        resource_id="vol-123",
        resource_type="AWS::EC2::Volume",
        title="Test finding",
        description="Test finding",
        severity="HIGH",
        recommendation="Test",
        estimated_monthly_savings=40.0,
        metadata={},
    )

    now = datetime(
        2026,
        9,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    priority = calculate_current_finding_priority(
        finding,
        now=now,
    )

    assert priority == {
        "age_days": 0,
        "priority_score": 50,
        "priority_label": "MEDIUM",
    }


def test_calculate_current_finding_priority_preserves_existing_age():
    finding = Finding(
        rule_id="EBS_CURRENTLY_UNATTACHED",
        account_id="123456789012",
        region="us-east-1",
        resource_arn=(
            "arn:aws:ec2:us-east-1:123456789012:"
            "volume/vol-123"
        ),
        resource_id="vol-123",
        resource_type="AWS::EC2::Volume",
        title="Test finding",
        description="Test finding",
        severity="LOW",
        recommendation="Test",
        estimated_monthly_savings=40.0,
        metadata={},
    )

    existing_item = {
        "first_seen": "2026-09-01T12:00:00+00:00",
    }

    now = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=timezone.utc,
    )

    priority = calculate_current_finding_priority(
        finding,
        existing_item=existing_item,
        now=now,
    )

    # 40 savings + 10 days old + 0 LOW severity
    assert priority == {
        "age_days": 10,
        "priority_score": 50,
        "priority_label": "MEDIUM",
    }