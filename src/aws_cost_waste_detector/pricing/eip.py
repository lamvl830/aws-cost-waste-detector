import json
from typing import Any, Protocol


class EipPriceProvider(Protocol):
    """
    Interface for retrieving idle public IPv4 pricing.
    """

    def get_hourly_price(
        self,
        *,
        region: str,
    ) -> float:
        """
        Return the hourly price for one idle public IPv4 address.
        """
        ...


class AwsEipPriceProvider:
    """
    Retrieve idle public IPv4 pricing from the AWS Price List API.
    """

    def __init__(self, pricing_client: Any):
        self.pricing_client = pricing_client

        # Cache prices by region so repeated EIP findings do not
        # trigger duplicate AWS Pricing API calls.
        self._price_cache: dict[str, float] = {}

    def get_hourly_price(
        self,
        *,
        region: str,
    ) -> float:
        """
        Return the hourly price for one idle public IPv4 address.

        The Price List query is filtered specifically for idle public
        IPv4 usage so unrelated EC2 products are not returned.
        """
        if region in self._price_cache:
            return self._price_cache[region]

        filters = [
            {
                "Type": "TERM_MATCH",
                "Field": "regionCode",
                "Value": region,
            },
            {
                "Type": "CONTAINS",
                "Field": "usagetype",
                "Value": "PublicIPv4:IdleAddress",
            },
        ]

        next_token = None

        while True:
            request = {
                "ServiceCode": "AmazonEC2",
                "Filters": filters,
                "MaxResults": 100,
            }

            if next_token is not None:
                request["NextToken"] = next_token

            response = self.pricing_client.get_products(
                ServiceCode="AmazonVPC",
                Filters=filters,
                MaxResults=100,
                **({"NextToken": next_token} if next_token else {}),
            )

            for raw_product in response.get("PriceList", []):
                product = (
                    json.loads(raw_product)
                    if isinstance(raw_product, str)
                    else raw_product
                )

                attributes = product.get(
                    "product",
                    {},
                ).get(
                    "attributes",
                    {},
                )

                usage_type = attributes.get(
                    "usagetype",
                    "",
                )

                if "PublicIPv4:IdleAddress" not in usage_type:
                    continue

                on_demand_terms = product.get(
                    "terms",
                    {},
                ).get(
                    "OnDemand",
                    {},
                )

                for term in on_demand_terms.values():
                    price_dimensions = term.get(
                        "priceDimensions",
                        {},
                    )

                    for dimension in price_dimensions.values():
                        if dimension.get("unit") != "Hrs":
                            continue

                        usd_price = dimension.get(
                            "pricePerUnit",
                            {},
                        ).get("USD")

                        if usd_price is not None:
                            price = float(usd_price)

                            self._price_cache[region] = price

                            return price

            next_token = response.get("NextToken")

            if not next_token:
                break

        raise LookupError(
            "No idle public IPv4 price found for "
            f"region={region}"
        )