DEFAULT_MONTHLY_HOURS = 730


def estimate_eip_monthly_cost(
    *,
    hourly_price: float,
    hours_per_month: int = DEFAULT_MONTHLY_HOURS,
) -> float:
    """
    Estimate the monthly cost of one public IPv4 address.

    The hourly price is supplied by the pricing layer so this
    calculation stays independent from AWS pricing retrieval.
    """
    if hourly_price < 0:
        raise ValueError("hourly_price cannot be negative")

    if hours_per_month < 0:
        raise ValueError("hours_per_month cannot be negative")

    monthly_cost = hourly_price * hours_per_month

    return round(monthly_cost, 2)