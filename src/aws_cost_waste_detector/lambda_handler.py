import logging
import os
from typing import Any

import boto3

from aws_cost_waste_detector.detector import run_detector
from aws_cost_waste_detector.html_report import render_html_report
from aws_cost_waste_detector.notifier import SnsNotifier
from aws_cost_waste_detector.report_publisher import S3ReportPublisher
from aws_cost_waste_detector.reporting import (
    build_cost_summary,
    format_cost_summary,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _parse_scan_regions(
    value: str | None,
    *,
    default_region: str,
) -> list[str]:
    """
    Parse the comma-separated SCAN_REGIONS environment variable.

    If SCAN_REGIONS is not configured, preserve the original
    single-region behavior by scanning the Lambda deployment region.
    """
    if not value:
        return [default_region]

    regions = []

    for raw_region in value.split(","):
        region = raw_region.strip()

        if region and region not in regions:
            regions.append(region)

    if not regions:
        raise RuntimeError(
            "SCAN_REGIONS must contain at least one AWS region"
        )

    return regions


def lambda_handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    """
    Run the cost-waste detector from AWS Lambda.

    The Lambda infrastructure remains in its deployment region while
    AWS resources can be scanned across multiple configured regions.
    """
    deployment_region = os.environ.get("AWS_REGION")

    if not deployment_region:
        raise RuntimeError(
            "AWS_REGION environment variable is not configured"
        )

    scan_regions = _parse_scan_regions(
        os.environ.get("SCAN_REGIONS"),
        default_region=deployment_region,
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
        region_name=deployment_region,
    )

    notifier = None

    if topic_arn:
        sns_client = session.client(
            "sns",
            region_name=deployment_region,
        )

        notifier = SnsNotifier(
            sns_client,
            topic_arn=topic_arn,
        )

    regional_results = []

    all_findings = []
    all_persistence_results = []
    all_resolution_results = []
    all_notification_results = []

    # Scan each configured region independently.
    #
    # DynamoDB remains in the Lambda deployment region while the EC2
    # client inside run_detector targets the individual scan region.
    for scan_region in scan_regions:
        logger.info(
            "Scanning AWS region: %s",
            scan_region,
        )

        result = run_detector(
            session,
            region=scan_region,
            storage_region=deployment_region,
            table_name=table_name,
            notifier=notifier,
            grace_period_days=grace_period_days,
        )

        regional_results.append(
            result
        )

        all_findings.extend(
            result["findings"]
        )

        all_persistence_results.extend(
            result["persistence_results"]
        )

        all_resolution_results.extend(
            result["resolution_results"]
        )

        all_notification_results.extend(
            result["notification_results"]
        )

    # scan_regions is guaranteed to contain at least one region.
    account_id = regional_results[0]["account_id"]

    # Build one consolidated summary across every scanned region.
    summary = build_cost_summary(
        all_findings
    )

    report_result = None
    report_notification_message_id = None

    # Use a readable region label inside the report/email while using a
    # stable path component for multi-region reports in S3.
    if len(scan_regions) == 1:
        report_region_display = scan_regions[0]
        report_scope = scan_regions[0]
    else:
        report_region_display = ", ".join(
            scan_regions
        )
        report_scope = "multi-region"

    if report_bucket:
        html = render_html_report(
            account_id=account_id,
            region=report_region_display,
            findings=all_findings,
            summary=summary,
        )

        s3_client = session.client(
            "s3",
            region_name=deployment_region,
        )

        report_publisher = S3ReportPublisher(
            s3_client,
            bucket_name=report_bucket,
        )

        report_result = report_publisher.publish(
            html=html,
            account_id=account_id,
            region=report_scope,
        )

        logger.info(
            "HTML report published to s3://%s/%s",
            report_result["bucket"],
            report_result["key"],
        )

        # Avoid sending a daily report email when nothing was found.
        if (
            notifier is not None
            and summary["total_findings"] > 0
        ):
            report_notification_message_id = (
                notifier.send_report_summary(
                    account_id=account_id,
                    region=report_region_display,
                    summary=summary,
                    report_url=report_result["url"],
                )
            )

            logger.info(
                "Report summary notification sent: %s",
                report_notification_message_id,
            )

    logger.info(
        "Scanned AWS regions: %s",
        scan_regions,
    )

    logger.info(
        "\n%s",
        format_cost_summary(
            summary
        ),
    )

    logger.info(
        "Persistence results: %s",
        all_persistence_results,
    )

    logger.info(
        "Resolution results: %s",
        all_resolution_results,
    )

    return {
        "account_id": account_id,
        "region": deployment_region,
        "scan_regions": scan_regions,
        "total_findings": len(
            all_findings
        ),
        "resolved_findings": len(
            all_resolution_results
        ),
        "notifications_sent": len(
            all_notification_results
        ),
        "report_notification_message_id": (
            report_notification_message_id
        ),
        "report": report_result,
        "summary": summary,
    }