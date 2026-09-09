from datetime import datetime, timezone

from aws_cost_waste_detector.models import Finding

SEVERITY_POINTS = {
    "LOW": 0,
    "MEDIUM": 5,
    "HIGH": 10,
    "CRITICAL": 15,
}


def calculate_age_days(
    *,
    first_seen: str,
    now: datetime | None = None,
) -> int:
    """
    Calculate how many whole days a finding has been active.

    first_seen is stored in DynamoDB as an ISO-8601 timestamp.
    """
    first_seen_datetime = datetime.fromisoformat(first_seen)

    if now is None:
        now = datetime.now(timezone.utc)

    age = now - first_seen_datetime

    if age.total_seconds() < 0:
        raise ValueError("first_seen cannot be in the future")

    return age.days


def calculate_priority_score(
    *,
    estimated_monthly_savings: float | None,
    age_days: int,
    severity: str,
    now: datetime | None = None,
) -> int:
    """
    Calculate a 0-100 priority score for a cost-waste finding.

    Score breakdown:
    - Monthly savings: up to 60 points
    - Finding age: up to 25 points
    - Severity: up to 15 points
    """
    if age_days < 0:
        raise ValueError("age_days cannot be negative")

    if estimated_monthly_savings is not None:
        if estimated_monthly_savings < 0:
            raise ValueError(
                "estimated_monthly_savings cannot be negative"
            )

        savings_score = min(
            int(round(estimated_monthly_savings)),
            60,
        )
    else:
        savings_score = 0

    age_score = min(
        age_days,
        25,
    )

    normalized_severity = severity.upper()

    if normalized_severity not in SEVERITY_POINTS:
        raise ValueError(
            f"Unsupported severity: {severity}"
        )

    severity_score = SEVERITY_POINTS[
        normalized_severity
    ]

    return (
        savings_score
        + age_score
        + severity_score
    )


def priority_label(score: int) -> str:
    """
    Convert a numeric priority score into a readable priority level.
    """
    if score < 0 or score > 100:
        raise ValueError(
            "score must be between 0 and 100"
        )

    if score >= 80:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"


def calculate_finding_priority(
        item: dict,
        *,
        now: datetime | None = None,
) -> dict[str, int | str]:
    """
    Calculate priority info for stored DynamoDB finding.

    The function derives finding age from first_seen and combines it.
    with estimated monthly savings and severity.
    """
    age_days = calculate_age_days(
        first_seen=item["first_seen"],
        now=now,
    )

    estimated_monthly_savings = item.get("estimated_monthly_savings")

    # DynamoDB may return numeric values as Decimal objects.
    # Convert to float before passing them into the scoring layer.
    if estimated_monthly_savings is not None:
        estimated_monthly_savings = float(
            estimated_monthly_savings
        )

    score = calculate_priority_score(
        estimated_monthly_savings=estimated_monthly_savings,
        age_days=age_days,
        severity=item["severity"],
    )  

    return {
        "age_days": age_days,
        "priority_score": score,
        "priority_label": priority_label(score),
    }


def calculate_current_finding_priority(
    finding: Finding,
    *,
    existing_item: dict | None = None,
    now: datetime | None = None,
) -> dict[str, int | str]:
    """
    Calculate priority for a finding returned by the current scan.

    Existing findings preserve their historical first_seen timestamp.
    Brand-new findings begin with an age of zero.

    Current savings and severity values always come from the latest scan.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if existing_item is not None:
        first_seen = existing_item["first_seen"]
    else:
        first_seen = now.isoformat()

    return calculate_finding_priority(
        {
            "first_seen": first_seen,
            "estimated_monthly_savings": (
                finding.estimated_monthly_savings
            ),
            "severity": finding.severity,
        },
        now=now,
    )