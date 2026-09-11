from datetime import datetime, timezone
from html import escape
from typing import Any
from urllib.parse import quote


def _format_currency(value: Any) -> str:
    """
    Format a numeric value as US currency.
    """
    return f"${float(value or 0):,.2f}"


def _build_console_url(
    finding: dict[str, Any],
) -> str | None:
    """
    Build an AWS Console link for supported finding types.

    The rule ID is used because it is stable within the detector and
    tells us which AWS console page should display the resource.
    """
    region = finding.get("region")
    resource_id = finding.get("resource_id")
    rule_id = finding.get("rule_id")

    if not region or not resource_id:
        return None

    encoded_region = quote(
        str(region),
        safe="",
    )

    encoded_resource_id = quote(
        str(resource_id),
        safe="",
    )

    base_url = (
        "https://console.aws.amazon.com/ec2/home"
        f"?region={encoded_region}"
    )

    if rule_id == "EBS_CURRENTLY_UNATTACHED":
        return (
            f"{base_url}"
            f"#Volumes:search={encoded_resource_id}"
        )

    if rule_id == "EIP_UNUSED":
        return (
            f"{base_url}"
            f"#Addresses:search={encoded_resource_id}"
        )

    return None


def _render_finding_row(
    finding: dict[str, Any],
) -> str:
    """
    Render one cost-waste finding as an HTML table row.
    """
    resource_id = escape(
        str(
            finding.get(
                "resource_id",
                "Unknown",
            )
        )
    )

    resource_type = escape(
        str(
            finding.get(
                "resource_type",
                "Unknown",
            )
        )
    )

    region = escape(
        str(
            finding.get(
                "region",
                "Unknown",
            )
        )
    )

    priority = escape(
        str(
            finding.get(
                "priority_label",
                "UNKNOWN",
            )
        )
    )

    severity = escape(
        str(
            finding.get(
                "severity",
                "UNKNOWN",
            )
        )
    )

    recommendation = escape(
        str(
            finding.get(
                "recommendation",
                "",
            )
        )
    )

    age_days = int(
        finding.get(
            "age_days",
            0,
        )
        or 0
    )

    savings = _format_currency(
        finding.get(
            "estimated_monthly_savings",
            0,
        )
    )

    console_url = _build_console_url(
        finding
    )

    if console_url:
        resource_display = (
            f'<a href="{escape(console_url)}">'
            f"{resource_id}"
            "</a>"
        )
    else:
        resource_display = resource_id

    return f"""
        <tr>
            <td>{priority}</td>
            <td>{severity}</td>
            <td>{resource_type}</td>
            <td>{resource_display}</td>
            <td>{region}</td>
            <td>{age_days}</td>
            <td>{savings}</td>
            <td>{recommendation}</td>
        </tr>
    """


def render_html_report(
    *,
    account_id: str,
    region: str,
    findings: list[dict[str, Any]],
    summary: dict[str, Any],
    generated_at: datetime | None = None,
) -> str:
    """
    Render a complete HTML cost-waste report.

    The report is intentionally self-contained so it can be stored
    directly in S3 without requiring JavaScript, external CSS, or
    another web application.
    """
    if generated_at is None:
        generated_at = datetime.now(
            timezone.utc
        )

    generated_display = (
        generated_at
        .astimezone(timezone.utc)
        .strftime("%Y-%m-%d %H:%M:%S UTC")
    )

    total_findings = int(
        summary.get(
            "total_findings",
            len(findings),
        )
    )

    monthly_savings = _format_currency(
        summary.get(
            "total_monthly_savings",
            0,
        )
    )

    annual_savings = _format_currency(
        summary.get(
            "total_annual_savings",
            0,
        )
    )

    if findings:
        finding_rows = "".join(
            _render_finding_row(finding)
            for finding in findings
        )

        findings_content = f"""
            <table>
                <thead>
                    <tr>
                        <th>Priority</th>
                        <th>Severity</th>
                        <th>Resource Type</th>
                        <th>Resource</th>
                        <th>Region</th>
                        <th>Age (Days)</th>
                        <th>Monthly Savings</th>
                        <th>Recommendation</th>
                    </tr>
                </thead>
                <tbody>
                    {finding_rows}
                </tbody>
            </table>
        """
    else:
        findings_content = """
            <div class="empty-state">
                No current cost-waste findings were detected.
            </div>
        """

    safe_account_id = escape(
        str(account_id)
    )

    safe_region = escape(
        str(region)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>AWS Cost Waste Report</title>

    <style>
        body {{
            font-family:
                Arial,
                Helvetica,
                sans-serif;
            margin: 0;
            background: #f5f6f8;
            color: #1f2937;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 32px;
        }}

        h1 {{
            margin-bottom: 8px;
        }}

        .metadata {{
            margin-bottom: 28px;
            color: #4b5563;
            line-height: 1.6;
        }}

        .summary {{
            display: grid;
            grid-template-columns:
                repeat(
                    auto-fit,
                    minmax(200px, 1fr)
                );
            gap: 16px;
            margin-bottom: 32px;
        }}

        .card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
        }}

        .card-label {{
            color: #6b7280;
            font-size: 14px;
        }}

        .card-value {{
            margin-top: 8px;
            font-size: 26px;
            font-weight: bold;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border: 1px solid #e5e7eb;
        }}

        th,
        td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
            vertical-align: top;
        }}

        th {{
            background: #f9fafb;
        }}

        a {{
            color: #2563eb;
        }}

        .empty-state {{
            background: white;
            padding: 32px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
        }}

        .notice {{
            margin-top: 32px;
            padding: 16px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            color: #4b5563;
            line-height: 1.6;
        }}
    </style>
</head>

<body>
    <main class="container">
        <h1>AWS Cost Waste Report</h1>

        <div class="metadata">
            <div>
                AWS Account:
                <strong>{safe_account_id}</strong>
            </div>

            <div>
                Region:
                <strong>{safe_region}</strong>
            </div>

            <div>
                Generated:
                <strong>{generated_display}</strong>
            </div>
        </div>

        <section class="summary">
            <div class="card">
                <div class="card-label">
                    Current Findings
                </div>

                <div class="card-value">
                    {total_findings}
                </div>
            </div>

            <div class="card">
                <div class="card-label">
                    Estimated Monthly Savings
                </div>

                <div class="card-value">
                    {monthly_savings}
                </div>
            </div>

            <div class="card">
                <div class="card-label">
                    Estimated Annual Savings
                </div>

                <div class="card-value">
                    {annual_savings}
                </div>
            </div>
        </section>

        <h2>Current Opportunities</h2>

        {findings_content}

        <div class="notice">
            <strong>Important:</strong>
            Savings values are estimates based on AWS pricing data
            and detected resource configuration. Actual savings may
            differ.

            <br><br>

            AWS Cost Waste Detector is read-only with respect to the
            AWS resources it evaluates. It identifies potential waste
            but does not automatically delete or modify customer
            resources.
        </div>
    </main>
</body>
</html>
"""