import argparse

import boto3

from aws_cost_waste_detector.pricing.eip import AwsEipPriceProvider


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for EIP pricing verification.
    """
    parser = argparse.ArgumentParser(
        description="Verify live AWS public IPv4 pricing retrieval"
    )

    parser.add_argument(
        "--profile",
        help="Optional AWS CLI profile name",
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region whose idle public IPv4 price should be retrieved",
    )

    return parser.parse_args()


def main() -> None:
    """
    Retrieve the live hourly price for an idle public IPv4 address.
    """
    args = parse_args()

    session = boto3.Session(
        profile_name=args.profile,
    )

    # The Pricing API endpoint region is separate from the region
    # whose product price we are looking up.
    pricing_client = session.client(
        "pricing",
        region_name="us-east-1",
    )

    provider = AwsEipPriceProvider(
        pricing_client,
    )

    hourly_price = provider.get_hourly_price(
        region=args.region,
    )

    monthly_cost = hourly_price * 730

    print(
        f"Idle public IPv4 in {args.region}: "
        f"${hourly_price:.4f} per hour"
    )

    print(
        f"Approximate monthly cost at 730 hours: "
        f"${monthly_cost:.2f}"
    )


if __name__ == "__main__":
    main()