import json
from typing import Any, Protocol


class EbsPriceProvider(Protocol):
    """
    Interface for retrieving EBS storage pricing.
    """

    def get_price_per_gib_month(
        self,
        *,
        region: str,
        volume_type: str,
    ) -> float:
        """
        Return the storage price for one GiB-month of an EBS volume.
        """
        ...


class AwsEbsPriceProvider:
    """
    Retrieve EBS storage pricing from the AWS Price List API.
    """

    def __init__(self, pricing_client: Any):
        self.pricing_client = pricing_client

        # Cache prices by region and volume type so multiple volumes of
        # the same type do not trigger duplicate AWS Pricing API calls.
        self._price_cache: dict[tuple[str, str], float] = {}

    def get_price_per_gib_month(
        self,
        *,
        region: str,
        volume_type: str,
    ) -> float:
        """
        Return the EBS storage price for one GiB-month.

        The target AWS region is supplied as a pricing filter rather
        than being inferred from the Pricing API client's endpoint.
        """
        cache_key = (
            region,
            volume_type,
        )

        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        response = self.pricing_client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {
                    "Type": "TERM_MATCH",
                    "Field": "productFamily",
                    "Value": "Storage",
                },
                {
                    "Type": "TERM_MATCH",
                    "Field": "volumeApiName",
                    "Value": volume_type,
                },
                {
                    "Type": "TERM_MATCH",
                    "Field": "regionCode",
                    "Value": region,
                },
            ],
            MaxResults=100,
        )

        for raw_product in response.get("PriceList", []):
            product = (
                json.loads(raw_product)
                if isinstance(raw_product, str)
                else raw_product
            )

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
                    # EBS storage pricing is expressed per GB-month.
                    if dimension.get("unit") != "GB-Mo":
                        continue

                    usd_price = dimension.get(
                        "pricePerUnit",
                        {},
                    ).get("USD")

                    if usd_price is not None:
                        price = float(usd_price)

                        self._price_cache[cache_key] = price

                        return price

        raise LookupError(
            "No EBS storage price found for "
            f"region={region}, volume_type={volume_type}"
        )