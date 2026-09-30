import json

from aws_cost_waste_detector.ec2_pricing import (
    Ec2OnDemandPriceProvider,
)


def _price_product(
    hourly_price: str,
) -> str:
    return json.dumps(
        {
            "terms": {
                "OnDemand": {
                    "offer": {
                        "priceDimensions": {
                            "dimension": {
                                "unit": "Hrs",
                                "pricePerUnit": {
                                    "USD": (
                                        hourly_price
                                    )
                                },
                            }
                        }
                    }
                }
            }
        }
    )


class FakePricingClient:
    def __init__(
        self,
        *,
        price_list,
    ):
        self.price_list = price_list
        self.requests = []

    def get_products(self, **kwargs):
        self.requests.append(
            kwargs
        )

        return {
            "PriceList": (
                self.price_list
            )
        }


def test_get_hourly_price_returns_linux_price():
    client = FakePricingClient(
        price_list=[
            _price_product(
                "0.0960000000"
            )
        ]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    price = provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
        platform_details="Linux/UNIX",
        tenancy="default",
    )

    assert price == 0.096

    request = client.requests[0]

    assert (
        request["ServiceCode"]
        == "AmazonEC2"
    )

    filters = {
        item["Field"]: item["Value"]
        for item in request["Filters"]
    }

    assert filters["instanceType"] == (
        "m5.large"
    )

    assert filters["regionCode"] == (
        "us-east-1"
    )

    assert filters["operatingSystem"] == (
        "Linux"
    )

    assert filters["tenancy"] == (
        "Shared"
    )


def test_get_hourly_price_maps_windows_platform():
    client = FakePricingClient(
        price_list=[
            _price_product(
                "0.1880000000"
            )
        ]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
        platform_details="Windows",
    )

    filters = {
        item["Field"]: item["Value"]
        for item
        in client.requests[0][
            "Filters"
        ]
    }

    assert (
        filters["operatingSystem"]
        == "Windows"
    )


def test_get_hourly_price_uses_cache():
    client = FakePricingClient(
        price_list=[
            _price_product(
                "0.0960000000"
            )
        ]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    first = provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
    )

    second = provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
    )

    assert first == 0.096
    assert second == 0.096

    assert len(client.requests) == 1


def test_get_hourly_price_returns_none_when_no_product_matches():
    client = FakePricingClient(
        price_list=[]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    price = provider.get_hourly_price(
        instance_type="example.type",
        region="us-east-1",
    )

    assert price is None


def test_get_hourly_price_rejects_unsupported_platform():
    client = FakePricingClient(
        price_list=[]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    price = provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
        platform_details="Red Hat Enterprise Linux",
    )

    assert price is None
    assert client.requests == []


def test_get_hourly_price_rejects_unknown_tenancy():
    client = FakePricingClient(
        price_list=[]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    price = provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
        tenancy="something-unknown",
    )

    assert price is None
    assert client.requests == []


def test_get_hourly_price_rejects_windows_byol():
    client = FakePricingClient(
        price_list=[]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    price = provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
        platform_details="Windows BYOL",
    )

    assert price is None
    assert client.requests == []


def test_get_hourly_price_rejects_dedicated_host_tenancy():
    client = FakePricingClient(
        price_list=[]
    )

    provider = (
        Ec2OnDemandPriceProvider(
            client
        )
    )

    price = provider.get_hourly_price(
        instance_type="m5.large",
        region="us-east-1",
        platform_details="Linux/UNIX",
        tenancy="host",
    )

    assert price is None
    assert client.requests == []