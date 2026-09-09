from collections.abc import Iterable
from typing import Any

from aws_cost_waste_detector.cost.ebs import estimate_ebs_monthly_cost
from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.pricing.ebs import EbsPriceProvider

IGNORE_TAG = "WasteDetectorIgnore"


def _tags_to_dict(
    tags: list[dict[str, str]] | None,
) -> dict[str, str]:
    return {
        tag["Key"]: tag["Value"]
        for tag in (tags or [])
    }


def _ignored(tags: dict[str, str]) -> bool:
    return tags.get(
        IGNORE_TAG,
        "",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
    }


def scan_unattached_ebs(
    ec2_client: Any,
    *,
    account_id: str,
    region: str,
    partition: str,
    price_provider: EbsPriceProvider | None = None,
) -> Iterable[Finding]:
    """
    Find EBS volumes that are currently unattached.

    EC2 DescribeVolumes does not expose when a volume was detached.
    The persistence layer tracks first_seen and last_seen so long-lived
    unattached volumes can later be promoted to actionable waste.

    When a price provider is supplied, the scanner also estimates the
    monthly savings from deleting the unused volume.
    """
    paginator = ec2_client.get_paginator(
        "describe_volumes"
    )

    for page in paginator.paginate(
        Filters=[
            {
                "Name": "status",
                "Values": ["available"],
            }
        ]
    ):
        for volume in page.get("Volumes", []):
            tags = _tags_to_dict(
                volume.get("Tags")
            )

            if _ignored(tags):
                continue

            volume_id = volume["VolumeId"]
            size_gib = volume.get("Size")
            volume_type = volume.get("VolumeType")
            name = tags.get("Name")

            label = (
                f"{name} ({volume_id})"
                if name
                else volume_id
            )

            description = (
                f"EBS volume {label} is currently unattached."
            )

            if size_gib is not None:
                description += f" Size: {size_gib} GiB."

            # Pricing is optional so the scanner can still operate
            # when no pricing provider is configured.
            estimated_monthly_savings = None

            if (
                price_provider is not None
                and size_gib is not None
                and volume_type is not None
            ):
                price_per_gib_month = (
                    price_provider.get_price_per_gib_month(
                        region=region,
                        volume_type=volume_type,
                    )
                )

                estimated_monthly_savings = (
                    estimate_ebs_monthly_cost(
                        size_gib=size_gib,
                        price_per_gib_month=price_per_gib_month,
                    )
                )

            yield Finding(
                rule_id="EBS_CURRENTLY_UNATTACHED",
                account_id=account_id,
                region=region,
                resource_arn=(
                    f"arn:{partition}:ec2:{region}:"
                    f"{account_id}:volume/{volume_id}"
                ),
                resource_id=volume_id,
                resource_type="AWS::EC2::Volume",
                title="EBS volume is currently unattached",
                description=description,
                severity="LOW",
                recommendation=(
                    "Track this finding over time. If the volume "
                    "remains unattached beyond the grace period, "
                    "verify it is no longer needed before "
                    "snapshotting or deleting it."
                ),
                estimated_monthly_savings=estimated_monthly_savings,
                metadata={
                    "size_gib": size_gib,
                    "volume_type": volume_type,
                    "availability_zone": volume.get(
                        "AvailabilityZone"
                    ),
                    "encrypted": volume.get("Encrypted"),
                    "name": name,
                    "tags": tags,
                },
            )