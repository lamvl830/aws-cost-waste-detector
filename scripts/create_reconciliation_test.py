import argparse

import boto3

from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.storage.dynamodb import save_finding


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the reconciliation test.
    """
    parser = argparse.ArgumentParser(
        description="Create a synthetic finding for reconciliation testing"
    )

    parser.add_argument(
        "--profile",
        help="Optional AWS CLI profile name",
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region",
    )

    parser.add_argument(
        "--table-name",
        default="WasteFindings",
        help="DynamoDB table name",
    )

    return parser.parse_args()


def main() -> None:
    """
    Create a synthetic active finding that the real scanner
    will later detect as missing and resolve.
    """
    args = parse_args()

    session = boto3.Session(
        profile_name=args.profile,
        region_name=args.region,
    )

    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    dynamodb = session.resource(
        "dynamodb",
        region_name=args.region,
    )

    table = dynamodb.Table(args.table_name)

    # This volume intentionally does not exist in AWS.
    # The real scanner therefore will not rediscover it,
    # allowing us to test the RESOLVED lifecycle transition.
    finding = Finding(
        rule_id="EBS_CURRENTLY_UNATTACHED",
        account_id=account_id,
        region=args.region,
        resource_arn=(
            f"arn:aws:ec2:{args.region}:{account_id}:"
            "volume/vol-reconciliation-test"
        ),
        resource_id="vol-reconciliation-test",
        resource_type="AWS::EC2::Volume",
        title="Synthetic reconciliation test",
        description="Temporary finding used to test resolution.",
        severity="LOW",
        recommendation="No action required.",
        estimated_monthly_savings=None,
        metadata={
            "synthetic": True,
        },
    )

    result = save_finding(
        table,
        finding,
    )

    print(
        f"Created test finding: "
        f"{finding.resource_id} -> {result}"
    )


if __name__ == "__main__":
    main()