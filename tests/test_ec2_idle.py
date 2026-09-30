from datetime import datetime, timedelta, timezone

from aws_cost_waste_detector.ec2_idle import (
    MEBIBYTE,
    Ec2IdleThresholds,
    Ec2Utilization,
    get_ec2_utilization,
    is_idle_ec2,
    scan_idle_ec2,
)


class FakeCloudWatchClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def get_metric_data(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


def test_get_ec2_utilization_summarizes_metrics():
    start_time = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    end_time = start_time + timedelta(
        hours=4
    )

    client = FakeCloudWatchClient(
        {
            "MetricDataResults": [
                {
                    "Id": "cpu_avg",
                    "Values": [
                        1.0,
                        2.0,
                        3.0,
                        2.0,
                    ],
                },
                {
                    "Id": "cpu_max",
                    "Values": [
                        5.0,
                        10.0,
                        8.0,
                        6.0,
                    ],
                },
                {
                    "Id": "network_in",
                    "Values": [
                        1 * MEBIBYTE,
                        2 * MEBIBYTE,
                        1 * MEBIBYTE,
                        1 * MEBIBYTE,
                    ],
                },
                {
                    "Id": "network_out",
                    "Values": [
                        2 * MEBIBYTE,
                        2 * MEBIBYTE,
                        1 * MEBIBYTE,
                        1 * MEBIBYTE,
                    ],
                },
            ]
        }
    )

    utilization = get_ec2_utilization(
        client,
        instance_id="i-example",
        start_time=start_time,
        end_time=end_time,
    )

    assert (
        utilization.average_cpu_percent
        == 2.0
    )

    assert (
        utilization.maximum_cpu_percent
        == 10.0
    )

    assert (
        utilization.network_in_bytes
        == 5 * MEBIBYTE
    )

    assert (
        utilization.network_out_bytes
        == 6 * MEBIBYTE
    )

    assert utilization.metric_coverage == 1.0

    request = client.requests[0]

    assert len(
        request["MetricDataQueries"]
    ) == 4

    assert {
        query["Id"]
        for query
        in request["MetricDataQueries"]
    } == {
        "cpu_avg",
        "cpu_max",
        "network_in",
        "network_out",
    }


def test_idle_ec2_returns_true_for_low_utilization():
    utilization = Ec2Utilization(
        average_cpu_percent=2.0,
        maximum_cpu_percent=10.0,
        network_in_bytes=20 * MEBIBYTE,
        network_out_bytes=10 * MEBIBYTE,
        metric_coverage=1.0,
    )

    assert is_idle_ec2(
        utilization
    )


def test_idle_ec2_rejects_high_average_cpu():
    utilization = Ec2Utilization(
        average_cpu_percent=15.0,
        maximum_cpu_percent=18.0,
        network_in_bytes=20 * MEBIBYTE,
        network_out_bytes=10 * MEBIBYTE,
        metric_coverage=1.0,
    )

    assert not is_idle_ec2(
        utilization
    )


def test_idle_ec2_rejects_bursty_cpu():
    utilization = Ec2Utilization(
        average_cpu_percent=3.0,
        maximum_cpu_percent=80.0,
        network_in_bytes=20 * MEBIBYTE,
        network_out_bytes=10 * MEBIBYTE,
        metric_coverage=1.0,
    )

    assert not is_idle_ec2(
        utilization
    )


def test_idle_ec2_rejects_high_network_usage():
    utilization = Ec2Utilization(
        average_cpu_percent=2.0,
        maximum_cpu_percent=10.0,
        network_in_bytes=500 * MEBIBYTE,
        network_out_bytes=10 * MEBIBYTE,
        metric_coverage=1.0,
    )

    assert not is_idle_ec2(
        utilization
    )


def test_idle_ec2_rejects_incomplete_metrics():
    utilization = Ec2Utilization(
        average_cpu_percent=2.0,
        maximum_cpu_percent=10.0,
        network_in_bytes=None,
        network_out_bytes=10 * MEBIBYTE,
        metric_coverage=1.0,
    )

    assert not is_idle_ec2(
        utilization
    )


def test_idle_ec2_rejects_low_metric_coverage():
    utilization = Ec2Utilization(
        average_cpu_percent=2.0,
        maximum_cpu_percent=10.0,
        network_in_bytes=20 * MEBIBYTE,
        network_out_bytes=10 * MEBIBYTE,
        metric_coverage=0.50,
    )

    assert not is_idle_ec2(
        utilization
    )


def test_idle_ec2_supports_custom_thresholds():
    utilization = Ec2Utilization(
        average_cpu_percent=8.0,
        maximum_cpu_percent=25.0,
        network_in_bytes=150 * MEBIBYTE,
        network_out_bytes=150 * MEBIBYTE,
        metric_coverage=1.0,
    )

    thresholds = Ec2IdleThresholds(
        average_cpu_percent=10.0,
        maximum_cpu_percent=30.0,
        network_in_bytes=200 * MEBIBYTE,
        network_out_bytes=200 * MEBIBYTE,
    )

    assert is_idle_ec2(
        utilization,
        thresholds=thresholds,
    )


class FakeEc2Paginator:
    def __init__(self, instances):
        self.instances = instances

    def paginate(self, *, Filters):
        return [
            {
                "Reservations": [
                    {
                        "Instances": (
                            self.instances
                        )
                    }
                ]
            }
        ]


class FakeEc2Client:
    def __init__(self, instances):
        self.instances = instances

    def get_paginator(
        self,
        operation_name,
    ):
        assert (
            operation_name
            == "describe_instances"
        )

        return FakeEc2Paginator(
            self.instances
        )


class FakePriceProvider:
    def __init__(
        self,
        hourly_price,
    ):
        self.hourly_price = (
            hourly_price
        )
        self.requests = []

    def get_hourly_price(
        self,
        *,
        instance_type,
        region,
        platform_details,
        tenancy,
    ):
        self.requests.append(
            {
                "instance_type": (
                    instance_type
                ),
                "region": region,
                "platform_details": (
                    platform_details
                ),
                "tenancy": tenancy,
            }
        )

        return self.hourly_price


def test_scan_idle_ec2_creates_finding():
    now = datetime(
        2026,
        9,
        29,
        tzinfo=timezone.utc,
    )

    instance = {
        "InstanceId": "i-idle",
        "InstanceType": "m5.large",
        "LaunchTime": (
            now - timedelta(days=30)
        ),
        "PlatformDetails": "Linux/UNIX",
        "UsageOperation": "RunInstances",
        "Placement": {
            "AvailabilityZone": (
                "us-east-1a"
            ),
            "Tenancy": "default",
        },
        "Tags": [
            {
                "Key": "Name",
                "Value": "idle-server",
            }
        ],
    }

    # Seven days of hourly metrics gives complete metric coverage.
    datapoints = 7 * 24

    cloudwatch = FakeCloudWatchClient(
        {
            "MetricDataResults": [
                {
                    "Id": "cpu_avg",
                    "Values": [
                        2.0
                    ] * datapoints,
                },
                {
                    "Id": "cpu_max",
                    "Values": [
                        10.0
                    ] * datapoints,
                },
                {
                    "Id": "network_in",
                    "Values": [
                        1000.0
                    ] * datapoints,
                },
                {
                    "Id": "network_out",
                    "Values": [
                        1000.0
                    ] * datapoints,
                },
            ]
        }
    )

    price_provider = (
        FakePriceProvider(
            0.096
        )
    )

    findings = list(
        scan_idle_ec2(
            FakeEc2Client(
                [instance]
            ),
            cloudwatch,
            account_id=(
                "123456789012"
            ),
            region="us-east-1",
            price_provider=(
                price_provider
            ),
            now=now,
        )
    )

    assert len(findings) == 1

    finding = findings[0]

    assert (
        finding.rule_id
        == "EC2_IDLE"
    )

    assert (
        finding.resource_id
        == "i-idle"
    )

    assert finding.resource_arn == (
        "arn:aws:ec2:us-east-1:"
        "123456789012:"
        "instance/i-idle"
    )

    assert (
        finding.resource_type
        == "AWS::EC2::Instance"
    )

    assert finding.severity == (
        "MEDIUM"
    )

    assert (
        finding.estimated_monthly_savings
        == 70.08
    )

    assert (
        finding.metadata[
            "instance_type"
        ]
        == "m5.large"
    )

    assert (
        finding.metadata[
            "average_cpu_percent"
        ]
        == 2.0
    )


def test_scan_idle_ec2_does_not_flag_active_instance():
    now = datetime(
        2026,
        9,
        29,
        tzinfo=timezone.utc,
    )

    instance = {
        "InstanceId": "i-active",
        "InstanceType": "m5.large",
        "LaunchTime": (
            now - timedelta(days=30)
        ),
        "Placement": {},
    }

    datapoints = 7 * 24

    cloudwatch = FakeCloudWatchClient(
        {
            "MetricDataResults": [
                {
                    "Id": "cpu_avg",
                    "Values": [
                        40.0
                    ] * datapoints,
                },
                {
                    "Id": "cpu_max",
                    "Values": [
                        80.0
                    ] * datapoints,
                },
                {
                    "Id": "network_in",
                    "Values": [
                        1000.0
                    ] * datapoints,
                },
                {
                    "Id": "network_out",
                    "Values": [
                        1000.0
                    ] * datapoints,
                },
            ]
        }
    )

    findings = list(
        scan_idle_ec2(
            FakeEc2Client(
                [instance]
            ),
            cloudwatch,
            account_id=(
                "123456789012"
            ),
            region="us-east-1",
            now=now,
        )
    )

    assert findings == []


def test_scan_idle_ec2_skips_new_instance():
    now = datetime(
        2026,
        9,
        29,
        tzinfo=timezone.utc,
    )

    instance = {
        "InstanceId": "i-new",
        "InstanceType": "t3.micro",
        "LaunchTime": (
            now - timedelta(days=2)
        ),
        "Placement": {},
    }

    cloudwatch = FakeCloudWatchClient(
        {
            "MetricDataResults": []
        }
    )

    findings = list(
        scan_idle_ec2(
            FakeEc2Client(
                [instance]
            ),
            cloudwatch,
            account_id=(
                "123456789012"
            ),
            region="us-east-1",
            now=now,
        )
    )

    assert findings == []

    # Do not query CloudWatch until the complete lookback window exists.
    assert (
        cloudwatch.requests
        == []
    )


def test_scan_idle_ec2_skips_spot_instance():
    now = datetime(
        2026,
        9,
        29,
        tzinfo=timezone.utc,
    )

    instance = {
        "InstanceId": "i-spot",
        "InstanceType": "c7g.large",
        "InstanceLifecycle": "spot",
        "LaunchTime": (
            now - timedelta(days=30)
        ),
        "Placement": {},
    }

    cloudwatch = FakeCloudWatchClient(
        {
            "MetricDataResults": []
        }
    )

    findings = list(
        scan_idle_ec2(
            FakeEc2Client(
                [instance]
            ),
            cloudwatch,
            account_id=(
                "123456789012"
            ),
            region="us-east-1",
            now=now,
        )
    )

    assert findings == []
    assert cloudwatch.requests == []


def test_scan_idle_ec2_skips_dedicated_host_instance():
    now = datetime(
        2026,
        9,
        29,
        tzinfo=timezone.utc,
    )

    instance = {
        "InstanceId": "i-dedicated-host",
        "InstanceType": "m5.large",
        "LaunchTime": (
            now - timedelta(days=30)
        ),
        "Placement": {
            "AvailabilityZone": (
                "us-east-1a"
            ),
            "Tenancy": "host",
        },
    }

    cloudwatch = FakeCloudWatchClient(
        {
            "MetricDataResults": []
        }
    )

    price_provider = FakePriceProvider(
        0.096
    )

    findings = list(
        scan_idle_ec2(
            FakeEc2Client(
                [instance]
            ),
            cloudwatch,
            account_id=(
                "123456789012"
            ),
            region="us-east-1",
            price_provider=(
                price_provider
            ),
            now=now,
        )
    )

    assert findings == []

    # Dedicated Hosts are intentionally unsupported by the per-instance
    # savings model, so neither metrics nor pricing should be queried.
    assert cloudwatch.requests == []
    assert price_provider.requests == []


def test_scan_idle_ec2_keeps_finding_when_price_unavailable():
    now = datetime(
        2026,
        9,
        29,
        tzinfo=timezone.utc,
    )

    instance = {
        "InstanceId": "i-unpriced",
        "InstanceType": "m5.large",
        "LaunchTime": (
            now - timedelta(days=30)
        ),
        "Placement": {},
    }

    datapoints = 7 * 24

    cloudwatch = FakeCloudWatchClient(
        {
            "MetricDataResults": [
                {
                    "Id": "cpu_avg",
                    "Values": [
                        1.0
                    ] * datapoints,
                },
                {
                    "Id": "cpu_max",
                    "Values": [
                        5.0
                    ] * datapoints,
                },
                {
                    "Id": "network_in",
                    "Values": [
                        100.0
                    ] * datapoints,
                },
                {
                    "Id": "network_out",
                    "Values": [
                        100.0
                    ] * datapoints,
                },
            ]
        }
    )

    price_provider = (
        FakePriceProvider(
            None
        )
    )

    findings = list(
        scan_idle_ec2(
            FakeEc2Client(
                [instance]
            ),
            cloudwatch,
            account_id=(
                "123456789012"
            ),
            region="us-east-1",
            price_provider=(
                price_provider
            ),
            now=now,
        )
    )

    assert len(findings) == 1

    assert (
        findings[0]
        .estimated_monthly_savings
        == 0.0
    )


def test_scan_idle_ec2_rejects_invalid_lookback():
    now = datetime(
        2026,
        9,
        29,
        tzinfo=timezone.utc,
    )

    try:
        list(
            scan_idle_ec2(
                FakeEc2Client([]),
                FakeCloudWatchClient({}),
                account_id=(
                    "123456789012"
                ),
                region="us-east-1",
                lookback_days=0,
                now=now,
            )
        )
    except ValueError as error:
        assert str(error) == (
            "lookback_days must be greater than zero"
        )
    else:
        raise AssertionError(
            "Expected ValueError"
        )