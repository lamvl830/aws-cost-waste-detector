"""AWS Pricing API provider for EC2 On-Demand compute prices."""

import json
from typing import Any


def _pricing_operating_system(
    platform_details: str,
) -> str | None:
    """
    Convert EC2 PlatformDetails into the operating-system value expected
    by the AWS Pricing API.

    Initial support intentionally covers standard Linux/UNIX and Windows
    instances only. Platforms with additional software or licensing are
    skipped rather than risk producing an inaccurate savings estimate.
    """
    normalized = platform_details.lower()

    # These platforms can include additional licensing costs and should not
    # be treated as ordinary Linux or Windows pricing.
    unsupported_platforms = (
        "red hat",
        "rhel",
        "suse",
        "sql server",
    )

    if any(
        platform in normalized
        for platform in unsupported_platforms
    ):
        return None

    if "windows" in normalized:
        return "Windows"

    if (
        "linux" in normalized
        or "unix" in normalized
    ):
        return "Linux"

    return None


def _pricing_tenancy(
    tenancy: str,
) -> str | None:
    """Convert EC2 tenancy into the AWS Pricing API tenancy value."""
    if tenancy == "default":
        return "Shared"

    if tenancy == "dedicated":
        return "Dedicated"

    if tenancy == "host":
        return "Host"

    return None


def _extract_hourly_price(
    price_list: list[str],
) -> float | None:
    """
    Extract the USD hourly On-Demand price from AWS Pricing API products.

    EC2 pricing responses contain nested products, terms, and price
    dimensions. Only dimensions billed in hours are considered.
    """
    for raw_product in price_list:
        product = json.loads(
            raw_product
        )

        on_demand_terms = (
            product.get("terms", {})
            .get("OnDemand", {})
        )

        for term in on_demand_terms.values():
            price_dimensions = term.get(
                "priceDimensions",
                {},
            )

            for dimension in (
                price_dimensions.values()
            ):
                if (
                    dimension.get("unit")
                    != "Hrs"
                ):
                    continue

                usd_price = (
                    dimension.get(
                        "pricePerUnit",
                        {},
                    ).get("USD")
                )

                if usd_price is None:
                    continue

                return float(
                    usd_price
                )

    return None


class Ec2OnDemandPriceProvider:
    """
    Retrieve and cache EC2 On-Demand hourly compute prices.

    The provider is independent from idle-instance logic so the same pricing
    implementation can later be reused for EC2 right-sizing comparisons.
    """

    def __init__(
        self,
        pricing_client: Any,
    ) -> None:
        self.pricing_client = (
            pricing_client
        )

        self._cache: dict[
            tuple[
                str,
                str,
                str,
                str,
            ],
            float | None,
        ] = {}

    def get_hourly_price(
        self,
        *,
        instance_type: str,
        region: str,
        platform_details: str = (
            "Linux/UNIX"
        ),
        tenancy: str = "default",
    ) -> float | None:
        """
        Return the EC2 On-Demand hourly compute price in USD.

        Returns None when the instance platform or tenancy is unsupported,
        or when AWS Pricing does not return a matching hourly price.
        """
        operating_system = (
            _pricing_operating_system(
                platform_details
            )
        )

        pricing_tenancy = (
            _pricing_tenancy(
                tenancy
            )
        )

        if (
            operating_system is None
            or pricing_tenancy is None
        ):
            return None

        cache_key = (
            region,
            instance_type,
            operating_system,
            pricing_tenancy,
        )

        if cache_key in self._cache:
            return self._cache[
                cache_key
            ]

        response = (
            self.pricing_client.get_products(
                ServiceCode="AmazonEC2",
                Filters=[
                    {
                        "Type": "TERM_MATCH",
                        "Field": (
                            "instanceType"
                        ),
                        "Value": (
                            instance_type
                        ),
                    },
                    {
                        "Type": "TERM_MATCH",
                        "Field": (
                            "regionCode"
                        ),
                        "Value": region,
                    },
                    {
                        "Type": "TERM_MATCH",
                        "Field": (
                            "operatingSystem"
                        ),
                        "Value": (
                            operating_system
                        ),
                    },
                    {
                        "Type": "TERM_MATCH",
                        "Field": "tenancy",
                        "Value": (
                            pricing_tenancy
                        ),
                    },
                    {
                        "Type": "TERM_MATCH",
                        "Field": (
                            "preInstalledSw"
                        ),
                        "Value": "NA",
                    },
                    {
                        "Type": "TERM_MATCH",
                        "Field": (
                            "capacitystatus"
                        ),
                        "Value": "Used",
                    },
                ],
                MaxResults=100,
            )
        )

        price = _extract_hourly_price(
            response.get(
                "PriceList",
                [],
            )
        )

        self._cache[
            cache_key
        ] = price

        return price