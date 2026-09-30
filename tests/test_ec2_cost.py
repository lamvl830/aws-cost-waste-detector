import pytest

from aws_cost_waste_detector.ec2_cost import (
    DEFAULT_HOURS_PER_MONTH,
    estimate_idle_ec2_monthly_savings,
    estimate_monthly_ec2_cost,
)


def test_estimate_monthly_ec2_cost():
    monthly_cost = estimate_monthly_ec2_cost(
        0.096
    )

    assert monthly_cost == 70.08


def test_idle_ec2_monthly_savings_matches_compute_cost():
    savings = (
        estimate_idle_ec2_monthly_savings(
            0.10
        )
    )

    assert savings == 73.00


def test_estimate_monthly_ec2_cost_supports_custom_hours():
    monthly_cost = estimate_monthly_ec2_cost(
        0.10,
        hours_per_month=100,
    )

    assert monthly_cost == 10.00


def test_estimate_monthly_ec2_cost_rejects_negative_price():
    with pytest.raises(
        ValueError,
        match="hourly_price cannot be negative",
    ):
        estimate_monthly_ec2_cost(
            -0.01
        )


def test_estimate_monthly_ec2_cost_rejects_invalid_hours():
    with pytest.raises(
        ValueError,
        match=(
            "hours_per_month must be greater than zero"
        ),
    ):
        estimate_monthly_ec2_cost(
            0.10,
            hours_per_month=0,
        )


def test_default_hours_per_month_is_730():
    assert DEFAULT_HOURS_PER_MONTH == 730