import pytest

from aws_cost_waste_detector.cost.ebs import estimate_ebs_monthly_cost


def test_estimate_ebs_monthly_cost():
    monthly_cost = estimate_ebs_monthly_cost(
        size_gib=100,
        price_per_gib_month=0.08,
    )

    assert monthly_cost == 8.00


def test_estimate_ebs_monthly_cost_rounds_to_cents():
    monthly_cost = estimate_ebs_monthly_cost(
        size_gib=37,
        price_per_gib_month=0.08123,
    )

    assert monthly_cost == 3.01


def test_estimate_ebs_monthly_cost_allows_zero_size():
    monthly_cost = estimate_ebs_monthly_cost(
        size_gib=0,
        price_per_gib_month=0.08,
    )

    assert monthly_cost == 0.00


def test_estimate_ebs_monthly_cost_rejects_negative_size():
    with pytest.raises(
        ValueError,
        match="size_gib cannot be negative",
    ):
        estimate_ebs_monthly_cost(
            size_gib=-1,
            price_per_gib_month=0.08,
        )


def test_estimate_ebs_monthly_cost_rejects_negative_price():
    with pytest.raises(
        ValueError,
        match="price_per_gib_month cannot be negative",
    ):
        estimate_ebs_monthly_cost(
            size_gib=100,
            price_per_gib_month=-0.08,
        )
