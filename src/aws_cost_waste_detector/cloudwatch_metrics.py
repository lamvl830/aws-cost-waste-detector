"""Reusable helpers for retrieving AWS CloudWatch metric data."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MetricQuery:
    """
    Describe one CloudWatch metric query.

    Keeping this abstraction service-agnostic allows the same metric reader
    to support EC2, RDS, and future AWS resource scanners.
    """

    query_id: str
    namespace: str
    metric_name: str
    dimensions: dict[str, str]
    statistic: str
    period_seconds: int = 3600


def _build_metric_data_query(
    query: MetricQuery,
) -> dict[str, Any]:
    """Convert a MetricQuery into the AWS GetMetricData request format."""
    return {
        "Id": query.query_id,
        "MetricStat": {
            "Metric": {
                "Namespace": query.namespace,
                "MetricName": query.metric_name,
                "Dimensions": [
                    {
                        "Name": name,
                        "Value": value,
                    }
                    for name, value in query.dimensions.items()
                ],
            },
            "Period": query.period_seconds,
            "Stat": query.statistic,
        },
        "ReturnData": True,
    }


def get_metric_data(
    cloudwatch_client: Any,
    *,
    queries: list[MetricQuery],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, list[float]]:
    """
    Retrieve CloudWatch metric values for a collection of metric queries.

    GetMetricData is used instead of making one API request per metric so
    scanners can retrieve several utilization signals efficiently.

    CloudWatch may paginate large responses, so all pages are combined.
    """
    if not queries:
        return {}

    query_ids = [
        query.query_id
        for query in queries
    ]

    if len(query_ids) != len(set(query_ids)):
        raise ValueError(
            "CloudWatch metric query IDs must be unique"
        )

    results: dict[str, list[float]] = {
        query.query_id: []
        for query in queries
    }

    metric_data_queries = [
        _build_metric_data_query(query)
        for query in queries
    ]

    next_token = None

    while True:
        request: dict[str, Any] = {
            "MetricDataQueries": metric_data_queries,
            "StartTime": start_time,
            "EndTime": end_time,
            "ScanBy": "TimestampAscending",
        }

        if next_token:
            request["NextToken"] = next_token

        response = cloudwatch_client.get_metric_data(
            **request
        )

        for metric_result in response.get(
            "MetricDataResults",
            [],
        ):
            query_id = metric_result.get("Id")

            if query_id not in results:
                continue

            results[query_id].extend(
                float(value)
                for value in metric_result.get(
                    "Values",
                    [],
                )
            )

        next_token = response.get(
            "NextToken"
        )

        if not next_token:
            break

    return results