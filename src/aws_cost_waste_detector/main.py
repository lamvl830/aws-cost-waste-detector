import argparse

import boto3

from aws_cost_waste_detector.detector import run_detector
from aws_cost_waste_detector.reporting import format_cost_summary


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments used by the scanner.
    """
    parser = argparse.ArgumentParser(
        description="Scan AWS for cost-waste findings"
    )

    parser.add_argument(
        "--profile",
        help="Optional AWS CLI profile name",
    )

    parser.add_argument(
        "--region",
        help="AWS region to scan",
    )

    parser.add_argument(
        "--table-name",
        default="WasteFindings",
        help="DynamoDB table used to store cost-waste findings",
    )

    return parser.parse_args()


def main() -> None:
    """
    Run the detector from the command line and print the results.
    """
    args = parse_args()

    session = boto3.Session(
        profile_name=args.profile,
        region_name=args.region,
    )

    region = session.region_name

    if not region:
        raise SystemExit(
            "No AWS region configured. "
            "Pass --region or configure a default AWS region."
        )

    result = run_detector(
        session,
        region=region,
        table_name=args.table_name,
    )

    print(
        format_cost_summary(
            result["summary"]
        )
    )

    print(
        "\nPersistence results:"
    )

    print(
        result["persistence_results"]
    )

    print(
        "\nResolution results:"
    )

    print(
        result["resolution_results"]
    )

    print(
        f"\nFound {len(result['findings'])} current "
        f"cost-waste finding(s) in {region}."
    )

    print(
        f"Resolved {len(result['resolution_results'])} "
        "previous finding(s)."
    )


if __name__ == "__main__":
    main()