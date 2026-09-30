from datetime import datetime, timezone

import pytest

from aws_cost_waste_detector.cloudwatch_metrics import (
    MetricQuery,
    get_metric_data,
)


class FakeCloudWatchClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get_metric_data(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def test_get_metric_data_returns_metric_values():
    client = FakeCloudWatchClient(
        [
            {
                "MetricDataResults": [
                    {
                        "Id": "cpu_avg",
                        "Values": [
                            1.5,
                            2.5,
                            3.5,
                        ],
                    },
                    {
                        "Id": "network_in",
                        "Values": [
                            100.0,
                            200.0,
                        ],
                    },
                ]
            }
        ]
    )

    start_time = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    end_time = datetime(
        2026,
        9,
        8,
        tzinfo=timezone.utc,
    )

    queries = [
        MetricQuery(
            query_id="cpu_avg",
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions={
                "InstanceId": "i-example",
            },
            statistic="Average",
        ),
        MetricQuery(
            query_id="network_in",
            namespace="AWS/EC2",
            metric_name="NetworkIn",
            dimensions={
                "InstanceId": "i-example",
            },
            statistic="Sum",
        ),
    ]

    results = get_metric_data(
        client,
        queries=queries,
        start_time=start_time,
        end_time=end_time,
    )

    assert results == {
        "cpu_avg": [
            1.5,
            2.5,
            3.5,
        ],
        "network_in": [
            100.0,
            200.0,
        ],
    }

    request = client.requests[0]

    assert request["StartTime"] == start_time
    assert request["EndTime"] == end_time
    assert request["ScanBy"] == (
        "TimestampAscending"
    )

    assert len(
        request["MetricDataQueries"]
    ) == 2


def test_get_metric_data_builds_cloudwatch_query():
    client = FakeCloudWatchClient(
        [
            {
                "MetricDataResults": []
            }
        ]
    )

    query = MetricQuery(
        query_id="cpu_avg",
        namespace="AWS/EC2",
        metric_name="CPUUtilization",
        dimensions={
            "InstanceId": "i-123456",
        },
        statistic="Average",
        period_seconds=3600,
    )

    now = datetime.now(
        timezone.utc
    )

    get_metric_data(
        client,
        queries=[query],
        start_time=now,
        end_time=now,
    )

    aws_query = (
        client.requests[0]
        ["MetricDataQueries"][0]
    )

    assert aws_query == {
        "Id": "cpu_avg",
        "MetricStat": {
            "Metric": {
                "Namespace": "AWS/EC2",
                "MetricName": (
                    "CPUUtilization"
                ),
                "Dimensions": [
                    {
                        "Name": "InstanceId",
                        "Value": "i-123456",
                    }
                ],
            },
            "Period": 3600,
            "Stat": "Average",
        },
        "ReturnData": True,
    }


def test_get_metric_data_handles_pagination():
    client = FakeCloudWatchClient(
        [
            {
                "MetricDataResults": [
                    {
                        "Id": "cpu_avg",
                        "Values": [
                            1.0,
                            2.0,
                        ],
                    }
                ],
                "NextToken": "next-page",
            },
            {
                "MetricDataResults": [
                    {
                        "Id": "cpu_avg",
                        "Values": [
                            3.0,
                            4.0,
                        ],
                    }
                ]
            },
        ]
    )

    query = MetricQuery(
        query_id="cpu_avg",
        namespace="AWS/EC2",
        metric_name="CPUUtilization",
        dimensions={
            "InstanceId": "i-example",
        },
        statistic="Average",
    )

    now = datetime.now(
        timezone.utc
    )

    results = get_metric_data(
        client,
        queries=[query],
        start_time=now,
        end_time=now,
    )

    assert results["cpu_avg"] == [
        1.0,
        2.0,
        3.0,
        4.0,
    ]

    assert len(client.requests) == 2

    assert (
        client.requests[1]["NextToken"]
        == "next-page"
    )


def test_get_metric_data_rejects_duplicate_query_ids():
    query_one = MetricQuery(
        query_id="cpu",
        namespace="AWS/EC2",
        metric_name="CPUUtilization",
        dimensions={
            "InstanceId": "i-one",
        },
        statistic="Average",
    )

    query_two = MetricQuery(
        query_id="cpu",
        namespace="AWS/EC2",
        metric_name="CPUUtilization",
        dimensions={
            "InstanceId": "i-two",
        },
        statistic="Average",
    )

    client = FakeCloudWatchClient(
        []
    )

    now = datetime.now(
        timezone.utc
    )

    with pytest.raises(
        ValueError,
        match=(
            "CloudWatch metric query IDs "
            "must be unique"
        ),
    ):
        get_metric_data(
            client,
            queries=[
                query_one,
                query_two,
            ],
            start_time=now,
            end_time=now,
        )


def test_get_metric_data_handles_empty_queries():
    client = FakeCloudWatchClient(
        []
    )

    now = datetime.now(
        timezone.utc
    )

    results = get_metric_data(
        client,
        queries=[],
        start_time=now,
        end_time=now,
    )

    assert results == {}
    assert client.requests == []