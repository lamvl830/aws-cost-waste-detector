from datetime import datetime, timezone

from aws_cost_waste_detector.ec2 import (
    list_running_instances,
)


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages
        self.filters = None

    def paginate(self, *, Filters):
        self.filters = Filters
        return self.pages


class FakeEc2Client:
    def __init__(self, pages):
        self.paginator = FakePaginator(
            pages
        )

    def get_paginator(self, operation_name):
        assert operation_name == (
            "describe_instances"
        )

        return self.paginator


def test_list_running_instances():
    launch_time = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    client = FakeEc2Client(
        [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": (
                                    "i-0123456789abcdef0"
                                ),
                                "InstanceType": (
                                    "m5.large"
                                ),
                                "LaunchTime": (
                                    launch_time
                                ),
                                "PlatformDetails": (
                                    "Linux/UNIX"
                                ),
                                "UsageOperation": (
                                    "RunInstances"
                                ),
                                "Placement": {
                                    "AvailabilityZone": (
                                        "us-east-1a"
                                    ),
                                    "Tenancy": (
                                        "default"
                                    ),
                                },
                                "Tags": [
                                    {
                                        "Key": "Name",
                                        "Value": (
                                            "example-server"
                                        ),
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    )

    instances = list_running_instances(
        client
    )

    assert instances == [
        {
            "instance_id": (
                "i-0123456789abcdef0"
            ),
            "instance_type": "m5.large",
            "name": "example-server",
            "launch_time": launch_time,
            "availability_zone": (
                "us-east-1a"
            ),
            "tenancy": "default",
            "platform_details": (
                "Linux/UNIX"
            ),
            "usage_operation": (
                "RunInstances"
            ),
            "instance_lifecycle": (
                "on-demand"
            ),
        }
    ]

    assert client.paginator.filters == [
        {
            "Name": (
                "instance-state-name"
            ),
            "Values": ["running"],
        }
    ]


def test_list_running_instances_handles_pagination():
    client = FakeEc2Client(
        [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-first",
                                "InstanceType": (
                                    "t3.micro"
                                ),
                                "Placement": {
                                    "AvailabilityZone": (
                                        "us-east-1a"
                                    )
                                },
                            }
                        ]
                    }
                ]
            },
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-second",
                                "InstanceType": (
                                    "t3.small"
                                ),
                                "Placement": {
                                    "AvailabilityZone": (
                                        "us-east-1b"
                                    )
                                },
                            }
                        ]
                    }
                ]
            },
        ]
    )

    instances = list_running_instances(
        client
    )

    assert [
        instance["instance_id"]
        for instance in instances
    ] == [
        "i-first",
        "i-second",
    ]


def test_list_running_instances_handles_missing_optional_fields():
    client = FakeEc2Client(
        [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": (
                                    "i-minimal"
                                ),
                                "InstanceType": (
                                    "t3.micro"
                                ),
                            }
                        ]
                    }
                ]
            }
        ]
    )

    instances = list_running_instances(
        client
    )

    assert instances == [
        {
            "instance_id": "i-minimal",
            "instance_type": "t3.micro",
            "name": None,
            "launch_time": None,
            "availability_zone": None,
            "tenancy": "default",
            "platform_details": (
                "Linux/UNIX"
            ),
            "usage_operation": None,
            "instance_lifecycle": (
                "on-demand"
            ),
        }
    ]


def test_list_running_instances_preserves_spot_lifecycle():
    client = FakeEc2Client(
        [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-spot",
                                "InstanceType": (
                                    "c7g.large"
                                ),
                                "InstanceLifecycle": (
                                    "spot"
                                ),
                            }
                        ]
                    }
                ]
            }
        ]
    )

    instances = list_running_instances(
        client
    )

    assert (
        instances[0][
            "instance_lifecycle"
        ]
        == "spot"
    )