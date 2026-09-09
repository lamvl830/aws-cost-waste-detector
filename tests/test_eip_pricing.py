import json

import pytest

from aws_cost_waste_detector.pricing.eip import AwsEipPriceProvider


class FakePricingClient:
    """
    Fake AWS Pricing client for EIP pricing tests.
    """

    def __init__(self, price_list=None):
        self.price_list = price_list or []
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)

        return {
            "PriceList": self.price_list,
        }


def make_idle_ipv4_product():
    return {
        "product": {
            "attributes": {
                "usagetype": "USE1-PublicIPv4:IdleAddress",
            }
        },
        "terms": {
            "OnDemand": {
                "term-1": {
                    "priceDimensions": {
                        "dimension-1": {
                            "unit": "Hrs",
                            "pricePerUnit": {
                                "USD": "0.0050000000",
                            },
                        }
                    }
                }
            }
        },
    }


def test_aws_eip_price_provider_returns_idle_ipv4_price():
    client = FakePricingClient(
        price_list=[
            json.dumps(make_idle_ipv4_product()),
        ]
    )

    provider = AwsEipPriceProvider(client)

    price = provider.get_hourly_price(
        region="us-east-1",
    )

    assert price == 0.005


def test_aws_eip_price_provider_caches_price():
    client = FakePricingClient(
        price_list=[
            json.dumps(make_idle_ipv4_product()),
        ]
    )

    provider = AwsEipPriceProvider(client)

    first_price = provider.get_hourly_price(
        region="us-east-1",
    )

    second_price = provider.get_hourly_price(
        region="us-east-1",
    )

    assert first_price == 0.005
    assert second_price == 0.005
    assert len(client.calls) == 1


def test_aws_eip_price_provider_raises_when_price_missing():
    client = FakePricingClient()

    provider = AwsEipPriceProvider(client)

    with pytest.raises(
        LookupError,
        match="No idle public IPv4 price found",
    ):
        provider.get_hourly_price(
            region="us-east-1",
        )