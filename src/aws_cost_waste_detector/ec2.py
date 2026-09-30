"""EC2 resource discovery helpers."""

from typing import Any


def _get_name_tag(tags: list[dict[str, str]] | None) -> str | None:
    """Return the EC2 Name tag when one is present."""
    if not tags:
        return None

    for tag in tags:
        if tag.get("Key") == "Name":
            return tag.get("Value")

    return None


def list_running_instances(
    ec2_client: Any,
) -> list[dict[str, Any]]:
    """
    Return normalized metadata for running EC2 instances.

    Resource discovery is kept separate from utilization analysis so the
    same EC2 inventory can later be reused by both idle-instance and
    right-sizing rules.
    """
    paginator = ec2_client.get_paginator(
        "describe_instances"
    )

    pages = paginator.paginate(
        Filters=[
            {
                "Name": "instance-state-name",
                "Values": ["running"],
            }
        ]
    )

    instances: list[dict[str, Any]] = []

    for page in pages:
        for reservation in page.get(
            "Reservations",
            [],
        ):
            for instance in reservation.get(
                "Instances",
                [],
            ):
                placement = instance.get(
                    "Placement",
                    {},
                )

                instances.append(
                    {
                        "instance_id": instance[
                            "InstanceId"
                        ],
                        "instance_type": instance[
                            "InstanceType"
                        ],
                        "name": _get_name_tag(
                            instance.get("Tags")
                        ),
                        "launch_time": instance.get(
                            "LaunchTime"
                        ),
                        "availability_zone": (
                            placement.get(
                                "AvailabilityZone"
                            )
                        ),
                        "tenancy": placement.get(
                            "Tenancy",
                            "default",
                        ),  
                        "platform_details": (
                            instance.get(
                                "PlatformDetails",
                                "Linux/UNIX",
                            )
                        ),
                        "usage_operation": (
                            instance.get(
                                "UsageOperation"
                            )
                        ),
                        "instance_lifecycle": (
                            instance.get(
                                "InstanceLifecycle",
                                "on-demand",
                            )
                        ),
                    }
                )

    return instances