from typing import Any


def build_cost_summary(
    findings: list[dict[str, Any]],
    *,
    top_limit: int = 5,
) -> dict[str, Any]:
    """
    Build a summary of the current cost-waste findings.

    The summary includes total estimated savings and the highest-priority
    opportunities so callers do not need to duplicate reporting logic.
    """
    if top_limit < 0:
        raise ValueError("top_limit cannot be negative")

    total_monthly_savings = sum(
        float(finding.get("estimated_monthly_savings") or 0)
        for finding in findings
    )

    ranked_findings = sorted(
        findings,
        key=lambda finding: finding.get(
            "priority_score",
            0,
        ),
        reverse=True,
    )

    return {
        "total_findings": len(findings),
        "total_monthly_savings": round(
            total_monthly_savings,
            2,
        ),
        "total_annual_savings": round(
            total_monthly_savings * 12,
            2,
        ),
        "top_opportunities": ranked_findings[
            :top_limit
        ],
    }


def format_cost_summary(
    summary: dict[str, Any],
) -> str:
    """
    Convert a cost summary into a readable console report.
    """
    lines = [
        "AWS Cost Waste Summary",
        "----------------------",
        (
            f"Total findings: "
            f"{summary['total_findings']}"
        ),
        (
            "Estimated monthly savings: "
            f"${summary['total_monthly_savings']:.2f}"
        ),
        (
            "Estimated annual savings: "
            f"${summary['total_annual_savings']:.2f}"
        ),
        "",
        "Top opportunities:",
    ]

    opportunities = summary[
        "top_opportunities"
    ]

    if not opportunities:
        lines.append(
            "No current cost-waste findings."
        )

        return "\n".join(lines)

    for index, finding in enumerate(
        opportunities,
        start=1,
    ):
        resource_id = finding.get(
            "resource_id",
            "unknown",
        )

        title = finding.get(
            "title",
            "Untitled finding",
        )

        monthly_savings = float(
            finding.get(
                "estimated_monthly_savings"
            )
            or 0
        )

        priority_label = finding.get(
            "priority_label",
            "LOW",
        )

        priority_score = finding.get(
            "priority_score",
            0,
        )

        lines.extend(
            [
                "",
                f"{index}. {resource_id}",
                f"   {title}",
                (
                    f"   Savings: "
                    f"${monthly_savings:.2f}/month"
                ),
                (
                    f"   Priority: "
                    f"{priority_label} "
                    f"({priority_score})"
                ),
            ]
        )

    return "\n".join(lines)