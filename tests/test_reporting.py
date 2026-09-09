import pytest

from aws_cost_waste_detector.reporting import (
    build_cost_summary,
    format_cost_summary,
)


def test_build_cost_summary():
    findings = [
        {
            "resource_id": "vol-123",
            "title": "Unattached EBS volume",
            "estimated_monthly_savings": 40.0,
            "priority_score": 65,
            "priority_label": "HIGH",
        },
        {
            "resource_id": "eipalloc-123",
            "title": "Unused Elastic IP",
            "estimated_monthly_savings": 3.65,
            "priority_score": 8,
            "priority_label": "LOW",
        },
    ]

    summary = build_cost_summary(
        findings
    )

    assert summary["total_findings"] == 2
    assert summary["total_monthly_savings"] == 43.65
    assert summary["total_annual_savings"] == 523.80


def test_build_cost_summary_handles_missing_savings():
    findings = [
        {
            "resource_id": "resource-123",
            "estimated_monthly_savings": None,
            "priority_score": 10,
        }
    ]

    summary = build_cost_summary(
        findings
    )

    assert summary["total_monthly_savings"] == 0.0
    assert summary["total_annual_savings"] == 0.0


def test_build_cost_summary_ranks_top_opportunities():
    findings = [
        {
            "resource_id": "low",
            "priority_score": 10,
        },
        {
            "resource_id": "high",
            "priority_score": 80,
        },
        {
            "resource_id": "medium",
            "priority_score": 40,
        },
    ]

    summary = build_cost_summary(
        findings,
        top_limit=2,
    )

    assert [
        item["resource_id"]
        for item in summary["top_opportunities"]
    ] == [
        "high",
        "medium",
    ]


def test_build_cost_summary_rejects_negative_limit():
    with pytest.raises(
        ValueError,
        match="top_limit cannot be negative",
    ):
        build_cost_summary(
            [],
            top_limit=-1,
        )


def test_format_cost_summary():
    summary = {
        "total_findings": 1,
        "total_monthly_savings": 40.0,
        "total_annual_savings": 480.0,
        "top_opportunities": [
            {
                "resource_id": "vol-123",
                "title": "Unattached EBS volume",
                "estimated_monthly_savings": 40.0,
                "priority_score": 65,
                "priority_label": "HIGH",
            }
        ],
    }

    report = format_cost_summary(
        summary
    )

    assert "AWS Cost Waste Summary" in report
    assert "Total findings: 1" in report
    assert "Estimated monthly savings: $40.00" in report
    assert "Estimated annual savings: $480.00" in report
    assert "vol-123" in report
    assert "Priority: HIGH (65)" in report