from datetime import datetime, timezone

from aws_cost_waste_detector.html_report import (
    render_html_report,
)


def test_render_html_report_contains_summary():
    html = render_html_report(
        account_id="123456789012",
        region="us-east-1",
        findings=[],
        summary={
            "total_findings": 2,
            "total_monthly_savings": 11.65,
            "total_annual_savings": 139.80,
        },
        generated_at=datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert "123456789012" in html
    assert "us-east-1" in html
    assert "$11.65" in html
    assert "$139.80" in html
    assert "2026-09-11 12:00:00 UTC" in html


def test_render_html_report_contains_finding():
    html = render_html_report(
        account_id="123456789012",
        region="us-east-1",
        findings=[
            {
                "rule_id": "EBS_CURRENTLY_UNATTACHED",
                "resource_id": "vol-123",
                "resource_type": "EBS_VOLUME",
                "region": "us-east-1",
                "severity": "MEDIUM",
                "priority_label": "HIGH",
                "age_days": 14,
                "estimated_monthly_savings": 8.0,
                "recommendation": (
                    "Delete the volume if it is no longer needed."
                ),
            }
        ],
        summary={
            "total_findings": 1,
            "total_monthly_savings": 8.0,
            "total_annual_savings": 96.0,
        },
    )

    assert "vol-123" in html
    assert "HIGH" in html
    assert "$8.00" in html
    assert "14" in html
    assert "Delete the volume" in html


def test_render_html_report_contains_console_link():
    html = render_html_report(
        account_id="123456789012",
        region="us-east-1",
        findings=[
            {
                "rule_id": "EBS_CURRENTLY_UNATTACHED",
                "resource_id": "vol-123",
                "resource_type": "EBS_VOLUME",
                "region": "us-east-1",
                "severity": "MEDIUM",
                "priority_label": "MEDIUM",
                "age_days": 7,
                "estimated_monthly_savings": 8.0,
                "recommendation": "Review this volume.",
            }
        ],
        summary={
            "total_findings": 1,
            "total_monthly_savings": 8.0,
            "total_annual_savings": 96.0,
        },
    )

    assert (
        "https://console.aws.amazon.com/ec2/home"
        "?region=us-east-1"
        "#Volumes:search=vol-123"
        in html
    )


def test_render_html_report_escapes_content():
    html = render_html_report(
        account_id="123456789012",
        region="us-east-1",
        findings=[
            {
                "rule_id": "EIP_UNUSED",
                "resource_id": "<script>alert(1)</script>",
                "resource_type": "EIP",
                "region": "us-east-1",
                "severity": "LOW",
                "priority_label": "LOW",
                "age_days": 0,
                "estimated_monthly_savings": 3.65,
                "recommendation": "<b>Release it</b>",
            }
        ],
        summary={
            "total_findings": 1,
            "total_monthly_savings": 3.65,
            "total_annual_savings": 43.80,
        },
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

    assert "<b>Release it</b>" not in html
    assert "&lt;b&gt;Release it&lt;/b&gt;" in html