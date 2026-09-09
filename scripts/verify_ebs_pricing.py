import argparse

import boto3

from aws_cost_waste_detector.pricing.ebs import AwsEbsPriceProvider


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the pricing verification script.
    """
    parser = argparse.ArgumentParser(
        description="Verify live AWS EBS pricing retrieval"
    )

    parser.add_argument(
        "--profile",
        help="Optional AWS CLI profile name",
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region whose EBS price should be retrieved",
    )

    parser.add_argument(
        "--volume-type",
        default="gp3",
        help="EBS volume type to price",
    )

    return parser.parse_args()


def main() -> None:
    """
    Retrieve a live EBS storage price from the AWS Price List API.
    """
    args = parse_args()

    session = boto3.Session(
        profile_name=args.profile,
    )

    # AWS Pricing is queried through its supported endpoint.
    # The actual target region is passed separately to our provider.
    pricing_client = session.client(
        "pricing",
        region_name="us-east-1",
    )

    provider = AwsEbsPriceProvider(
        pricing_client,
    )

    price = provider.get_price_per_gib_month(
        region=args.region,
        volume_type=args.volume_type,
    )

    print(
        f"{args.volume_type} storage in {args.region}: "
        f"${price:.4f} per GiB-month"
    )

    print(
        f"Example 100 GiB monthly storage cost: "
        f"${100 * price:.2f}"
    )


if __name__ == "__main__":
    main()