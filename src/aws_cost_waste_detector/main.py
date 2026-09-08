import argparse
import json

import boto3

from aws_cost_waste_detector.scanners.ebs import scan_unattached_ebs
from aws_cost_waste_detector.scanners.eip import scan_unused_eips


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan AWS for cost-waste findings")
    parser.add_argument("--profile", help="Optional AWS CLI profile name")
    parser.add_argument("--region", help="AWS region to scan")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    session = boto3.Session(
        profile_name=args.profile,
        region_name=args.region,
    )

    region = session.region_name

    if not region:
        raise SystemExit(
            "No AWS region configured. Pass --region or configure a default AWS region."
        )

    sts = session.client("sts")
    identity = sts.get_caller_identity()

    account_id = identity["Account"]
    partition = identity["Arn"].split(":", 2)[1]

    ec2 = session.client("ec2", region_name=region)

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

    print(
        json.dumps(
            [finding.to_dict() for finding in findings],
            indent=2,
        )
    )

    print(f"\nFound {len(findings)} cost-waste finding(s) in {region}.")


if __name__ == "__main__":
    main()