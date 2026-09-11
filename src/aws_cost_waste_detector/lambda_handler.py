import logging
import os
from typing import Any

import boto3

from aws_cost_waste_detector.detector import run_detector
from aws_cost_waste_detector.reporting import format_cost_summary
from aws_cost_waste_detector.notifier import SnsNotifier

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    """
    Run the cost-waste detector from AWS Lambda.

    Lambda supplies credentials automatically through its execution
    role, so no local AWS profile is required.
    """
    region = os.environ.get("AWS_REGION")

    if not region:
        raise RuntimeError(
            "AWS_REGION environment variable is not configured"
        )

    table_name = os.environ.get(
        "WASTE_FINDINGS_TABLE",
        "WasteFindings",
    )

    session = boto3.Session(
        region_name=region,
    )

    topic_arn = os.environ.get(
    "COST_WASTE_ALERTS_TOPIC_ARN"
    )

    notifier = None

    if topic_arn:
        sns_client = session.client(
            "sns",
            region_name=region,
        )

        notifier = SnsNotifier(
            sns_client,
            topic_arn=topic_arn,
        )

    result = run_detector(
        session,
        region=region,
        table_name=table_name,
        notifier=notifier,
    )

    # CloudWatch Logs will capture this readable summary.
    logger.info(
        "\n%s",
        format_cost_summary(
            result["summary"]
        ),
    )

    logger.info(
        "Persistence results: %s",
        result["persistence_results"],
    )

    logger.info(
        "Resolution results: %s",
        result["resolution_results"],
    )

    return {
        "account_id": result["account_id"],
        "region": result["region"],
        "total_findings": len(
            result["findings"]
        ),
        "resolved_findings": len(
            result["resolution_results"]
        ),
        "notifications_sent": len(
        result["notification_results"]
        ),
        "summary": result["summary"],
    }