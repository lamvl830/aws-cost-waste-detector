import argparse
import json

import boto3

from aws_cost_waste_detector.scanners.ebs import scan_unattached_ebs
from aws_cost_waste_detector.scanners.eip import scan_unused_eips
from aws_cost_waste_detector.storage.dynamodb import save_finding


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
    Run all configured AWS cost-waste scanners and persist
    discovered findings to DynamoDB.
    """
    args = parse_args()

    # Create an AWS session using the optional CLI profile and region.
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

    # Determine which AWS account and partition the scanner is running against.
    sts = session.client("sts")
    identity = sts.get_caller_identity()

    account_id = identity["Account"]
    partition = identity["Arn"].split(":", 2)[1]

    # Create AWS service clients/resources used by the application.
    ec2 = session.client(
        "ec2",
        region_name=region,
    )

    dynamodb_resource = session.resource(
        "dynamodb",
        region_name=region,
    )

    table = dynamodb_resource.Table(args.table_name)

    # Collect findings from all registered scanners.
    findings = list(
        scan_unattached_ebs(
            ec2,
            account_id=account_id,
            region=region,
            partition=partition,
        )
    )

    findings.extend(
        scan_unused_eips(
            ec2,
            account_id=account_id,
            region=region,
            partition=partition,
        )
    )

    # Persist each finding to DynamoDB.
    #
    # save_finding() returns:
    # CREATED -> finding was seen for the first time
    # UPDATED -> finding already existed and last_seen was refreshed
    persistence_results = []

    for finding in findings:
        result = save_finding(
            table,
            finding,
        )

        persistence_results.append(
            {
                "resource_id": finding.resource_id,
                "rule_id": finding.rule_id,
                "result": result,
            }
        )

    # Print the findings themselves.
    print(
        json.dumps(
            [finding.to_dict() for finding in findings],
            indent=2,
        )
    )

    # Print what happened when each finding was persisted.
    print("\nPersistence results:")

    print(
        json.dumps(
            persistence_results,
            indent=2,
        )
    )

    print(
        f"\nFound {len(findings)} cost-waste finding(s) "
        f"in {region}."
    )


if __name__ == "__main__":
    main()