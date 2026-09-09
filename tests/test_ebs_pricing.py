import json

import pytest

from aws_cost_waste_detector.pricing.ebs import (
    AwsEbsPriceProvider,
    EbsPriceProvider,
)


class FakeEbsPriceProvider:
    """
    Fake implementation of the pricing interface.
    """

    def get_price_per_gib_month(
        self,
        *,
        region: str,
        volume_type: str,
    ) -> float:
        assert region == "us-east-1"
        assert volume_type == "gp3"

        return 0.08


class FakePricingClient:
    """
    Fake AWS Pricing client used to test price retrieval without
    making real AWS API calls.
    """

    def __init__(self, price_list=None):
        self.price_list = price_list or []
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)

        return {
            "PriceList": self.price_list,
        }


def get_test_price(
    provider: EbsPriceProvider,
) -> float:
    """
    Retrieve a price through the provider interface.
    """
    return provider.get_price_per_gib_month(
        region="us-east-1",
        volume_type="gp3",
    )


def test_ebs_price_provider_interface():
    provider = FakeEbsPriceProvider()

    price = get_test_price(provider)

    assert price == 0.08


def test_aws_ebs_price_provider_returns_storage_price():
    product = {
        "terms": {
            "OnDemand": {
                "term-1": {
                    "priceDimensions": {
                        "dimension-1": {
                            "unit": "GB-Mo",
                            "pricePerUnit": {
                                "USD": "0.0800000000",
                            },
                        }
                    }
                }
            }
        }
    }

    client = FakePricingClient(
        price_list=[
            json.dumps(product),
        ]
    )

    provider = AwsEbsPriceProvider(client)

    price = provider.get_price_per_gib_month(
        region="us-east-1",
        volume_type="gp3",
    )

    assert price == 0.08

    call = client.calls[0]

    assert {
        "Type": "TERM_MATCH",
        "Field": "volumeApiName",
        "Value": "gp3",
    } in call["Filters"]

    assert {
        "Type": "TERM_MATCH",
        "Field": "regionCode",
        "Value": "us-east-1",
    } in call["Filters"]


def test_aws_ebs_price_provider_raises_when_price_missing():
    client = FakePricingClient()

    provider = AwsEbsPriceProvider(client)

    with pytest.raises(
        LookupError,
        match="No EBS storage price found",
    ):
        provider.get_price_per_gib_month(
            region="us-east-1",
            volume_type="gp3",
        )


def test_aws_ebs_price_provider_caches_price():
    product = {
        "terms": {
            "OnDemand": {
                "term-1": {
                    "priceDimensions": {
                        "dimension-1": {
                            "unit": "GB-Mo",
                            "pricePerUnit": {
                                "USD": "0.0800000000",
                            },
                        }
                    }
                }
            }
        }
    }

    client = FakePricingClient(
        price_list=[
            json.dumps(product),
        ]
    )

    provider = AwsEbsPriceProvider(client)

    first_price = provider.get_price_per_gib_month(
        region="us-east-1",
        volume_type="gp3",
    )

    second_price = provider.get_price_per_gib_month(
        region="us-east-1",
        volume_type="gp3",
    )

    assert first_price == 0.08
    assert second_price == 0.08

    # The second lookup should come from the in-memory cache.
    assert len(client.calls) == 1