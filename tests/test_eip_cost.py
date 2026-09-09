import pytest

from aws_cost_waste_detector.cost.eip import estimate_eip_monthly_cost


def test_estimate_eip_monthly_cost():
    monthly_cost = estimate_eip_monthly_cost(
        hourly_price=0.005,
    )

    assert monthly_cost == 3.65


def test_estimate_eip_monthly_cost_custom_hours():
    monthly_cost = estimate_eip_monthly_cost(
        hourly_price=0.005,
        hours_per_month=744,
    )

    assert monthly_cost == 3.72


def test_estimate_eip_monthly_cost_zero_price():
    monthly_cost = estimate_eip_monthly_cost(
        hourly_price=0.0,
    )

    assert monthly_cost == 0.0


def test_estimate_eip_monthly_cost_rejects_negative_price():
    with pytest.raises(
        ValueError,
        match="hourly_price cannot be negative",
    ):
        estimate_eip_monthly_cost(
            hourly_price=-0.005,
        )


def test_estimate_eip_monthly_cost_rejects_negative_hours():
    with pytest.raises(
        ValueError,
        match="hours_per_month cannot be negative",
    ):
        estimate_eip_monthly_cost(
            hourly_price=0.005,
            hours_per_month=-1,
        )