"""Idle EC2 utilization analysis."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from aws_cost_waste_detector.ec2 import (
    list_running_instances,
)
from aws_cost_waste_detector.ec2_cost import (
    estimate_idle_ec2_monthly_savings,
)
from aws_cost_waste_detector.ec2_pricing import (
    Ec2OnDemandPriceProvider,
)
from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.cloudwatch_metrics import (
    MetricQuery,
    get_metric_data,
)


MEBIBYTE = 1024 * 1024


@dataclass(frozen=True)
class Ec2IdleThresholds:
    """
    Thresholds used to determine whether an EC2 instance appears idle.

    Conservative defaults reduce the chance of flagging an instance that
    has low average CPU but still receives meaningful bursts or network
    traffic.
    """

    average_cpu_percent: float = 5.0
    maximum_cpu_percent: float = 20.0
    network_in_bytes: float = 100 * MEBIBYTE
    network_out_bytes: float = 100 * MEBIBYTE
    minimum_metric_coverage: float = 0.80


@dataclass(frozen=True)
class Ec2Utilization:
    """Summarized EC2 utilization over a lookback window."""

    average_cpu_percent: float | None
    maximum_cpu_percent: float | None
    network_in_bytes: float | None
    network_out_bytes: float | None
    metric_coverage: float


def get_ec2_utilization(
    cloudwatch_client: Any,
    *,
    instance_id: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 3600,
) -> Ec2Utilization:
    """
    Retrieve and summarize EC2 utilization for one instance.

    Four signals are collected:
    - average CPU utilization
    - maximum CPU utilization
    - total inbound network traffic
    - total outbound network traffic

    Missing metric data is intentionally preserved instead of being treated
    as zero. Missing telemetry should not cause an instance to be classified
    as idle.
    """
    queries = [
        MetricQuery(
            query_id="cpu_avg",
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions={
                "InstanceId": instance_id,
            },
            statistic="Average",
            period_seconds=period_seconds,
        ),
        MetricQuery(
            query_id="cpu_max",
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions={
                "InstanceId": instance_id,
            },
            statistic="Maximum",
            period_seconds=period_seconds,
        ),
        MetricQuery(
            query_id="network_in",
            namespace="AWS/EC2",
            metric_name="NetworkIn",
            dimensions={
                "InstanceId": instance_id,
            },
            statistic="Sum",
            period_seconds=period_seconds,
        ),
        MetricQuery(
            query_id="network_out",
            namespace="AWS/EC2",
            metric_name="NetworkOut",
            dimensions={
                "InstanceId": instance_id,
            },
            statistic="Sum",
            period_seconds=period_seconds,
        ),
    ]

    values = get_metric_data(
        cloudwatch_client,
        queries=queries,
        start_time=start_time,
        end_time=end_time,
    )

    cpu_average_values = values["cpu_avg"]
    cpu_maximum_values = values["cpu_max"]
    network_in_values = values["network_in"]
    network_out_values = values["network_out"]

    lookback_seconds = (
        end_time - start_time
    ).total_seconds()

    expected_datapoints = max(
        1,
        int(
            lookback_seconds
            // period_seconds
        ),
    )

    datapoint_counts = [
        len(cpu_average_values),
        len(cpu_maximum_values),
        len(network_in_values),
        len(network_out_values),
    ]

    # Use the least complete metric as the coverage value. This prevents
    # missing network or CPU telemetry from being interpreted as zero usage.
    metric_coverage = min(
        datapoint_counts
    ) / expected_datapoints

    metric_coverage = min(
        metric_coverage,
        1.0,
    )

    return Ec2Utilization(
        average_cpu_percent=(
            sum(cpu_average_values)
            / len(cpu_average_values)
            if cpu_average_values
            else None
        ),
        maximum_cpu_percent=(
            max(cpu_maximum_values)
            if cpu_maximum_values
            else None
        ),
        network_in_bytes=(
            sum(network_in_values)
            if network_in_values
            else None
        ),
        network_out_bytes=(
            sum(network_out_values)
            if network_out_values
            else None
        ),
        metric_coverage=metric_coverage,
    )


def is_idle_ec2(
    utilization: Ec2Utilization,
    *,
    thresholds: Ec2IdleThresholds | None = None,
) -> bool:
    """
    Return whether EC2 utilization satisfies the idle thresholds.

    Insufficient or missing CloudWatch data returns False. It is safer to
    miss a possible optimization than to recommend stopping an instance
    when telemetry is incomplete.
    """
    if thresholds is None:
        thresholds = Ec2IdleThresholds()

    metrics = (
        utilization.average_cpu_percent,
        utilization.maximum_cpu_percent,
        utilization.network_in_bytes,
        utilization.network_out_bytes,
    )

    if any(
        value is None
        for value in metrics
    ):
        return False

    if (
        utilization.metric_coverage
        < thresholds.minimum_metric_coverage
    ):
        return False

    return (
        utilization.average_cpu_percent
        <= thresholds.average_cpu_percent
        and utilization.maximum_cpu_percent
        <= thresholds.maximum_cpu_percent
        and utilization.network_in_bytes
        <= thresholds.network_in_bytes
        and utilization.network_out_bytes
        <= thresholds.network_out_bytes
    )

def scan_idle_ec2(
    ec2_client: Any,
    cloudwatch_client: Any,
    *,
    account_id: str,
    region: str,
    partition: str = "aws",
    price_provider: Ec2OnDemandPriceProvider | None = None,
    lookback_days: int = 7,
    thresholds: Ec2IdleThresholds | None = None,
    now: datetime | None = None,
) -> Iterable[Finding]:
    """
    Scan running EC2 instances for sustained low utilization.

    Only On-Demand instances that have existed for the complete lookback
    window are evaluated. Spot instances are skipped because this detector
    currently estimates savings using On-Demand pricing.

    Missing pricing does not suppress an otherwise valid finding. In that
    case the finding is emitted with zero estimated savings rather than
    inventing a price.
    """
    if lookback_days <= 0:
        raise ValueError(
            "lookback_days must be greater than zero"
        )

    if thresholds is None:
        thresholds = Ec2IdleThresholds()

    if now is None:
        now = datetime.now(
            timezone.utc
        )

    start_time = now - timedelta(
        days=lookback_days
    )

    for instance in list_running_instances(
        ec2_client
    ):
        instance_id = instance[
            "instance_id"
        ]

        # Spot pricing is dynamic and requires a different pricing model.
        # Avoid presenting On-Demand savings estimates for Spot instances.
        if (
            instance["instance_lifecycle"]
            != "on-demand"
        ):
            continue

        launch_time = instance.get(
            "launch_time"
        )

        # A newly launched instance has not existed for the full evaluation
        # window and therefore should not yet be classified as idle.
        if (
            launch_time is None
            or launch_time > start_time
        ):
            continue

        utilization = get_ec2_utilization(
            cloudwatch_client,
            instance_id=instance_id,
            start_time=start_time,
            end_time=now,
        )

        if not is_idle_ec2(
            utilization,
            thresholds=thresholds,
        ):
            continue

        hourly_price = None

        if price_provider is not None:
            hourly_price = (
                price_provider.get_hourly_price(
                    instance_type=instance[
                        "instance_type"
                    ],
                    region=region,
                    platform_details=instance[
                        "platform_details"
                    ],
                    tenancy=instance[
                        "tenancy"
                    ],
                )
            )

        estimated_monthly_savings = 0.0

        if hourly_price is not None:
            estimated_monthly_savings = (
                estimate_idle_ec2_monthly_savings(
                    hourly_price
                )
            )

        resource_arn = (
            f"arn:{partition}:ec2:"
            f"{region}:{account_id}:"
            f"instance/{instance_id}"
        )

        instance_name = (
            instance.get("name")
            or instance_id
        )

        yield Finding(
            rule_id="EC2_IDLE",
            account_id=account_id,
            region=region,
            resource_arn=resource_arn,
            resource_id=instance_id,
            resource_type="AWS::EC2::Instance",
            title="EC2 instance appears idle",
            description=(
                f"EC2 instance {instance_name} has sustained "
                f"low CPU and network utilization over the "
                f"last {lookback_days} days."
            ),
            severity="MEDIUM",
            recommendation=(
                "Review the instance workload and consider stopping, "
                "terminating, or consolidating the instance if it is "
                "no longer required."
            ),
            estimated_monthly_savings=(
                estimated_monthly_savings
            ),
            metadata={
                "name": instance.get(
                    "name"
                ),
                "instance_type": instance[
                    "instance_type"
                ],
                "availability_zone": (
                    instance.get(
                        "availability_zone"
                    )
                ),
                "platform_details": instance[
                    "platform_details"
                ],
                "tenancy": instance[
                    "tenancy"
                ],
                "launch_time": (
                    launch_time.isoformat()
                ),
                "lookback_days": (
                    lookback_days
                ),
                "average_cpu_percent": (
                    utilization
                    .average_cpu_percent
                ),
                "maximum_cpu_percent": (
                    utilization
                    .maximum_cpu_percent
                ),
                "network_in_bytes": (
                    utilization
                    .network_in_bytes
                ),
                "network_out_bytes": (
                    utilization
                    .network_out_bytes
                ),
                "metric_coverage": (
                    utilization
                    .metric_coverage
                ),
                "hourly_compute_price": (
                    hourly_price
                ),
            },
        )