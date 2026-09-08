from collections.abc import Iterable
from typing import Any

from aws_cost_waste_detector.models import Finding

IGNORE_TAG = "WasteDetectorIgnore"


def _tags_to_dict(tags: list[dict[str, str]] | None) -> dict[str, str]:
    return {tag["Key"]: tag["Value"] for tag in (tags or [])}


def _ignored(tags: dict[str, str]) -> bool:
    return tags.get(IGNORE_TAG, "").strip().lower() in {"1", "true", "yes"}


def scan_unattached_ebs(
    ec2_client: Any,
    *,
    account_id: str,
    region: str,
    partition: str = "aws",
) -> Iterable[Finding]:
    """Find EBS volumes that are currently unattached.

    Important: EC2 DescribeVolumes does not expose when a volume was detached.
    This scanner therefore reports CURRENTLY_UNATTACHED. A persistence layer will
    later track first_seen/last_seen and promote long-lived findings to actionable
    waste after a configured grace period.
    """
    paginator = ec2_client.get_paginator("describe_volumes")

    for page in paginator.paginate(
        Filters=[{"Name": "status", "Values": ["available"]}]
    ):
        for volume in page.get("Volumes", []):
            tags = _tags_to_dict(volume.get("Tags"))
            if _ignored(tags):
                continue

            volume_id = volume["VolumeId"]
            size_gib = volume.get("Size")
            volume_type = volume.get("VolumeType")
            name = tags.get("Name")

            label = f"{name} ({volume_id})" if name else volume_id
            description = f"EBS volume {label} is currently unattached."
            if size_gib is not None:
                description += f" Size: {size_gib} GiB."

            yield Finding(
                rule_id="EBS_CURRENTLY_UNATTACHED",
                account_id=account_id,
                region=region,
                resource_arn=(
                    f"arn:{partition}:ec2:{region}:{account_id}:volume/{volume_id}"
                ),
                resource_id=volume_id,
                resource_type="AWS::EC2::Volume",
                title="EBS volume is currently unattached",
                description=description,
                severity="LOW",
                recommendation=(
                    "Track this finding over time. If the volume remains unattached "
                    "beyond the grace period, verify it is no longer needed before "
                    "snapshotting or deleting it."
                ),
                metadata={
                    "size_gib": size_gib,
                    "volume_type": volume_type,
                    "availability_zone": volume.get("AvailabilityZone"),
                    "encrypted": volume.get("Encrypted"),
                    "name": name,
                    "tags": tags,
                },
            )
