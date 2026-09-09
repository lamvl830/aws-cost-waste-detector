import argparse

import boto3

from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.storage.dynamodb import save_finding


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the persistence verification script.
    """
    parser = argparse.ArgumentParser(
        description="Verify DynamoDB finding persistence"
    )

    parser.add_argument(
        "--profile",
        help="Optional AWS CLI profile name",
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region containing the DynamoDB table",
    )

    parser.add_argument(
        "--table-name",
        default="WasteFindings",
        help="DynamoDB table used to store findings",
    )

    return parser.parse_args()


def main() -> None:
    """
    Create or update a synthetic finding to verify real DynamoDB persistence.
    """
    args = parse_args()

    session = boto3.Session(
        profile_name=args.profile,
        region_name=args.region,
    )

    # Determine the current AWS account dynamically instead of
    # hardcoding an account ID into the repository.
    sts = session.client("sts")
    identity = sts.get_caller_identity()

    account_id = identity["Account"]
    partition = identity["Arn"].split(":", 2)[1]

    dynamodb = session.resource(
        "dynamodb",
        region_name=args.region,
    )

    table = dynamodb.Table(args.table_name)

    # Synthetic finding used only to verify the persistence layer.
    finding = Finding(
        rule_id="TEST_PERSISTENCE",
        account_id=account_id,
        region=args.region,
        resource_arn=(
            f"arn:{partition}:ec2:{args.region}:{account_id}:"
            "volume/vol-test-persistence"
        ),
        resource_id="vol-test-persistence",
        resource_type="AWS::EC2::Volume",
        title="Persistence test finding",
        description="Synthetic finding used to verify DynamoDB persistence.",
        severity="LOW",
        recommendation="No action required. This is a test record.",
        estimated_monthly_savings=None,
        metadata={
            "synthetic": True,
        },
    )

    result = save_finding(
        table,
        finding,
    )

    print(f"Persistence result: {result}")


if __name__ == "__main__":
    main()