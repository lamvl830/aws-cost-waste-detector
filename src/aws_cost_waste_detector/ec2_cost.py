"""EC2 cost estimation helpers."""


DEFAULT_HOURS_PER_MONTH = 730


def estimate_monthly_ec2_cost(
    hourly_price: float,
    *,
    hours_per_month: int = DEFAULT_HOURS_PER_MONTH,
) -> float:
    """
    Estimate monthly EC2 compute cost from an hourly On-Demand price.

    AWS months vary in length, so the detector uses approximately
    730 hours per month for consistent savings estimates.
    """
    if hourly_price < 0:
        raise ValueError(
            "hourly_price cannot be negative"
        )

    if hours_per_month <= 0:
        raise ValueError(
            "hours_per_month must be greater than zero"
        )

    return round(
        hourly_price * hours_per_month,
        2,
    )


def estimate_idle_ec2_monthly_savings(
    hourly_price: float,
    *,
    hours_per_month: int = DEFAULT_HOURS_PER_MONTH,
) -> float:
    """
    Estimate monthly savings for an idle EC2 instance.

    An idle-instance recommendation assumes the On-Demand compute charge
    could be avoided if the instance were stopped or terminated after review.

    Attached storage and other AWS charges are intentionally not included.
    """
    return estimate_monthly_ec2_cost(
        hourly_price,
        hours_per_month=hours_per_month,
    )