def estimate_ebs_monthly_cost(
    *,
    size_gib: int,
    price_per_gib_month: float,
) -> float:
    """
    Estimate the monthly storage cost of an EBS volume.

    The caller supplies the current price per GiB-month so pricing
    retrieval remains separate from cost calculation.
    """
    if size_gib < 0:
        raise ValueError("size_gib cannot be negative")

    if price_per_gib_month < 0:
        raise ValueError("price_per_gib_month cannot be negative")

    monthly_cost = size_gib * price_per_gib_month

    return round(monthly_cost, 2)