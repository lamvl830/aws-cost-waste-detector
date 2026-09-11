import logging
import os
from typing import Any

import boto3

from aws_cost_waste_detector.detector import run_detector
from aws_cost_waste_detector.html_report import render_html_report
from aws_cost_waste_detector.notifier import SnsNotifier
from aws_cost_waste_detector.report_publisher import S3ReportPublisher
from aws_cost_waste_detector.reporting import format_cost_summary

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

    topic_arn = os.environ.get(
        "COST_WASTE_ALERTS_TOPIC_ARN"
    )

    report_bucket = os.environ.get(
        "REPORT_BUCKET"
    )

    grace_period_raw = os.environ.get(
        "FINDING_GRACE_PERIOD_DAYS",
        "7",
    )

    try:
        grace_period_days = int(
            grace_period_raw
        )
    except ValueError as error:
        raise RuntimeError(
            "FINDING_GRACE_PERIOD_DAYS must be an integer"
        ) from error

    if grace_period_days < 0:
        raise RuntimeError(
            "FINDING_GRACE_PERIOD_DAYS cannot be negative"
        )

    session = boto3.Session(
        region_name=region,
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
        grace_period_days=grace_period_days,
    )

    report_result = None
    report_notification_message_id = None

    if report_bucket:
        html = render_html_report(
            account_id=result["account_id"],
            region=result["region"],
            findings=result["findings"],
            summary=result["summary"],
        )

        s3_client = session.client(
            "s3",
            region_name=region,
        )

        report_publisher = S3ReportPublisher(
            s3_client,
            bucket_name=report_bucket,
        )

        report_result = report_publisher.publish(
            html=html,
            account_id=result["account_id"],
            region=result["region"],
        )

        logger.info(
            "HTML report published to s3://%s/%s",
            report_result["bucket"],
            report_result["key"],
        )

        # Avoid sending a daily empty-report email.
        if (
            notifier is not None
            and result["summary"]["total_findings"] > 0
        ):
            report_notification_message_id = (
                notifier.send_report_summary(
                    account_id=result["account_id"],
                    region=result["region"],
                    summary=result["summary"],
                    report_url=report_result["url"],
                )
            )

            logger.info(
                "Report summary notification sent: %s",
                report_notification_message_id,
            )

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
        "report_notification_message_id": (
            report_notification_message_id
        ),
        "report": report_result,
        "summary": result["summary"],
    }