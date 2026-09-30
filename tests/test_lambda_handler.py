import pytest

import aws_cost_waste_detector.lambda_handler as handler_module


MEBIBYTE = 1024 * 1024


class FakeSession:
    """
    Minimal boto3 Session replacement used by Lambda handler tests.
    """

    def __init__(self, region_name=None):
        self.region_name = region_name
        self.client_calls = []

    def client(
        self,
        service_name,
        region_name=None,
    ):
        self.client_calls.append(
            {
                "service_name": service_name,
                "region_name": region_name,
            }
        )

        return {
            "service_name": service_name,
            "region_name": region_name,
        }


def _clear_optional_environment(
    monkeypatch,
):
    """
    Remove optional Lambda settings so tests do not depend on the
    developer machine's environment.
    """
    environment_variables = [
        "SCAN_REGIONS",
        "WASTE_FINDINGS_TABLE",
        "COST_WASTE_ALERTS_TOPIC_ARN",
        "REPORT_BUCKET",
        "FINDING_GRACE_PERIOD_DAYS",
        "EC2_IDLE_LOOKBACK_DAYS",
        "EC2_IDLE_AVERAGE_CPU_THRESHOLD_PERCENT",
        "EC2_IDLE_MAXIMUM_CPU_THRESHOLD_PERCENT",
        "EC2_IDLE_NETWORK_IN_THRESHOLD_MIB",
        "EC2_IDLE_NETWORK_OUT_THRESHOLD_MIB",
        "EC2_IDLE_MINIMUM_METRIC_COVERAGE",
    ]

    for variable in environment_variables:
        monkeypatch.delenv(
            variable,
            raising=False,
        )


def _make_detector_result(
    *,
    region="us-east-1",
    findings=None,
):
    if findings is None:
        findings = []

    return {
        "account_id": "123456789012",
        "region": region,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "total_monthly_savings": 0.0,
            "total_annual_savings": 0.0,
            "top_opportunities": [],
        },
        "persistence_results": [],
        "resolution_results": [],
        "notification_results": [],
    }


def test_lambda_handler_runs_detector(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "WASTE_FINDINGS_TABLE",
        "TestWasteFindings",
    )

    monkeypatch.setattr(
        handler_module.boto3,
        "Session",
        FakeSession,
    )

    calls = {}

    def fake_run_detector(
        session,
        *,
        region,
        storage_region=None,
        table_name,
        notifier=None,
        grace_period_days=7,
        ec2_idle_lookback_days=7,
        ec2_idle_thresholds=None,
    ):
        calls["session"] = session
        calls["region"] = region
        calls["storage_region"] = storage_region
        calls["table_name"] = table_name
        calls["notifier"] = notifier
        calls["grace_period_days"] = (
            grace_period_days
        )
        calls["ec2_idle_lookback_days"] = (
            ec2_idle_lookback_days
        )
        calls["ec2_idle_thresholds"] = (
            ec2_idle_thresholds
        )

        return _make_detector_result(
            findings=[
                {
                    "resource_id": "vol-123",
                    "region": "us-east-1",
                    "estimated_monthly_savings": 8.0,
                    "severity": "MEDIUM",
                    "priority_score": 20,
                    "priority_label": "LOW",
                }
            ],
        )

    monkeypatch.setattr(
        handler_module,
        "run_detector",
        fake_run_detector,
    )

    result = handler_module.lambda_handler(
        {},
        None,
    )

    assert calls["region"] == "us-east-1"

    assert (
        calls["storage_region"]
        == "us-east-1"
    )

    assert (
        calls["table_name"]
        == "TestWasteFindings"
    )

    assert calls["notifier"] is None

    assert (
        calls["grace_period_days"]
        == 7
    )

    assert (
        calls["ec2_idle_lookback_days"]
        == 7
    )

    thresholds = calls[
        "ec2_idle_thresholds"
    ]

    assert (
        thresholds.average_cpu_percent
        == 5.0
    )

    assert (
        thresholds.maximum_cpu_percent
        == 20.0
    )

    assert (
        thresholds.network_in_bytes
        == 100 * MEBIBYTE
    )

    assert (
        thresholds.network_out_bytes
        == 100 * MEBIBYTE
    )

    assert (
        thresholds.minimum_metric_coverage
        == 0.80
    )

    assert result["account_id"] == (
        "123456789012"
    )

    assert result["region"] == (
        "us-east-1"
    )

    assert result["scan_regions"] == [
        "us-east-1"
    ]

    assert result["total_findings"] == 1


def test_lambda_handler_requires_region(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    monkeypatch.delenv(
        "AWS_REGION",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "AWS_REGION environment variable "
            "is not configured"
        ),
    ):
        handler_module.lambda_handler(
            {},
            None,
        )


def test_lambda_handler_uses_configured_grace_period(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "FINDING_GRACE_PERIOD_DAYS",
        "3",
    )

    monkeypatch.setattr(
        handler_module.boto3,
        "Session",
        FakeSession,
    )

    calls = {}

    def fake_run_detector(
        session,
        *,
        region,
        storage_region=None,
        table_name,
        notifier=None,
        grace_period_days=7,
        ec2_idle_lookback_days=7,
        ec2_idle_thresholds=None,
    ):
        calls["grace_period_days"] = (
            grace_period_days
        )

        return _make_detector_result(
            region=region,
        )

    monkeypatch.setattr(
        handler_module,
        "run_detector",
        fake_run_detector,
    )

    handler_module.lambda_handler(
        {},
        None,
    )

    assert (
        calls["grace_period_days"]
        == 3
    )


def test_lambda_handler_rejects_invalid_grace_period(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "FINDING_GRACE_PERIOD_DAYS",
        "invalid",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "FINDING_GRACE_PERIOD_DAYS "
            "must be an integer"
        ),
    ):
        handler_module.lambda_handler(
            {},
            None,
        )


def test_lambda_handler_rejects_negative_grace_period(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "FINDING_GRACE_PERIOD_DAYS",
        "-1",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "FINDING_GRACE_PERIOD_DAYS "
            "must be at least 0"
        ),
    ):
        handler_module.lambda_handler(
            {},
            None,
        )


def test_lambda_handler_publishes_html_report(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "WASTE_FINDINGS_TABLE",
        "TestWasteFindings",
    )

    monkeypatch.setenv(
        "REPORT_BUCKET",
        "test-report-bucket",
    )

    monkeypatch.setattr(
        handler_module.boto3,
        "Session",
        FakeSession,
    )

    def fake_run_detector(
        session,
        *,
        region,
        storage_region=None,
        table_name,
        notifier=None,
        grace_period_days=7,
        ec2_idle_lookback_days=7,
        ec2_idle_thresholds=None,
    ):
        return _make_detector_result(
            region=region,
        )

    monkeypatch.setattr(
        handler_module,
        "run_detector",
        fake_run_detector,
    )

    monkeypatch.setattr(
        handler_module,
        "render_html_report",
        lambda **kwargs: (
            "<html>report</html>"
        ),
    )

    class FakePublisher:
        def __init__(
            self,
            s3_client,
            *,
            bucket_name,
        ):
            assert (
                bucket_name
                == "test-report-bucket"
            )

        def publish(
            self,
            *,
            html,
            account_id,
            region,
        ):
            assert (
                html
                == "<html>report</html>"
            )

            assert (
                account_id
                == "123456789012"
            )

            assert region == "us-east-1"

            return {
                "bucket": (
                    "test-report-bucket"
                ),
                "key": (
                    "reports/test.html"
                ),
                "url": (
                    "https://example.com/report"
                ),
            }

    monkeypatch.setattr(
        handler_module,
        "S3ReportPublisher",
        FakePublisher,
    )

    result = handler_module.lambda_handler(
        {},
        None,
    )

    assert result["report"] == {
        "bucket": "test-report-bucket",
        "key": "reports/test.html",
        "url": "https://example.com/report",
    }


def test_parse_scan_regions_defaults_to_lambda_region():
    regions = (
        handler_module._parse_scan_regions(
            None,
            default_region="us-east-1",
        )
    )

    assert regions == [
        "us-east-1"
    ]


def test_parse_scan_regions_supports_multiple_regions():
    regions = (
        handler_module._parse_scan_regions(
            "us-east-1,us-east-2,us-west-2",
            default_region="us-east-1",
        )
    )

    assert regions == [
        "us-east-1",
        "us-east-2",
        "us-west-2",
    ]


def test_parse_scan_regions_removes_duplicates_and_whitespace():
    regions = (
        handler_module._parse_scan_regions(
            (
                " us-east-1, us-east-2, "
                "us-east-1 "
            ),
            default_region="us-east-1",
        )
    )

    assert regions == [
        "us-east-1",
        "us-east-2",
    ]


def test_lambda_handler_scans_multiple_regions(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "SCAN_REGIONS",
        (
            "us-east-1,"
            "us-east-2,"
            "us-west-2"
        ),
    )

    monkeypatch.setenv(
        "WASTE_FINDINGS_TABLE",
        "TestWasteFindings",
    )

    monkeypatch.setattr(
        handler_module.boto3,
        "Session",
        FakeSession,
    )

    calls = []

    def fake_run_detector(
        session,
        *,
        region,
        storage_region=None,
        table_name,
        notifier=None,
        grace_period_days=7,
        ec2_idle_lookback_days=7,
        ec2_idle_thresholds=None,
    ):
        calls.append(
            {
                "region": region,
                "storage_region": (
                    storage_region
                ),
            }
        )

        return _make_detector_result(
            region=region,
            findings=[
                {
                    "resource_id": (
                        f"resource-{region}"
                    ),
                    "region": region,
                    "estimated_monthly_savings": 5.0,
                    "severity": "MEDIUM",
                    "priority_score": 10,
                    "priority_label": "LOW",
                }
            ],
        )

    monkeypatch.setattr(
        handler_module,
        "run_detector",
        fake_run_detector,
    )

    result = handler_module.lambda_handler(
        {},
        None,
    )

    assert calls == [
        {
            "region": "us-east-1",
            "storage_region": "us-east-1",
        },
        {
            "region": "us-east-2",
            "storage_region": "us-east-1",
        },
        {
            "region": "us-west-2",
            "storage_region": "us-east-1",
        },
    ]

    assert result["scan_regions"] == [
        "us-east-1",
        "us-east-2",
        "us-west-2",
    ]

    assert result["total_findings"] == 3

    assert (
        result["summary"][
            "total_monthly_savings"
        ]
        == 15.0
    )


def test_ec2_idle_configuration_uses_defaults(
    monkeypatch,
):
    _clear_optional_environment(
        monkeypatch
    )

    (
        lookback_days,
        thresholds,
    ) = (
        handler_module
        ._load_ec2_idle_configuration()
    )

    assert lookback_days == 7

    assert (
        thresholds.average_cpu_percent
        == 5.0
    )

    assert (
        thresholds.maximum_cpu_percent
        == 20.0
    )

    assert (
        thresholds.network_in_bytes
        == 100 * MEBIBYTE
    )

    assert (
        thresholds.network_out_bytes
        == 100 * MEBIBYTE
    )

    assert (
        thresholds.minimum_metric_coverage
        == 0.80
    )


def test_ec2_idle_configuration_reads_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "EC2_IDLE_LOOKBACK_DAYS",
        "14",
    )

    monkeypatch.setenv(
        "EC2_IDLE_AVERAGE_CPU_THRESHOLD_PERCENT",
        "4.5",
    )

    monkeypatch.setenv(
        "EC2_IDLE_MAXIMUM_CPU_THRESHOLD_PERCENT",
        "15",
    )

    monkeypatch.setenv(
        "EC2_IDLE_NETWORK_IN_THRESHOLD_MIB",
        "250",
    )

    monkeypatch.setenv(
        "EC2_IDLE_NETWORK_OUT_THRESHOLD_MIB",
        "300",
    )

    monkeypatch.setenv(
        "EC2_IDLE_MINIMUM_METRIC_COVERAGE",
        "0.9",
    )

    (
        lookback_days,
        thresholds,
    ) = (
        handler_module
        ._load_ec2_idle_configuration()
    )

    assert lookback_days == 14

    assert (
        thresholds.average_cpu_percent
        == 4.5
    )

    assert (
        thresholds.maximum_cpu_percent
        == 15.0
    )

    assert (
        thresholds.network_in_bytes
        == 250 * MEBIBYTE
    )

    assert (
        thresholds.network_out_bytes
        == 300 * MEBIBYTE
    )

    assert (
        thresholds.minimum_metric_coverage
        == 0.9
    )


def test_ec2_idle_configuration_rejects_invalid_lookback(
    monkeypatch,
):
    monkeypatch.setenv(
        "EC2_IDLE_LOOKBACK_DAYS",
        "0",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "EC2_IDLE_LOOKBACK_DAYS "
            "must be at least 1"
        ),
    ):
        (
            handler_module
            ._load_ec2_idle_configuration()
        )


def test_ec2_idle_configuration_rejects_average_cpu_above_maximum(
    monkeypatch,
):
    monkeypatch.setenv(
        "EC2_IDLE_AVERAGE_CPU_THRESHOLD_PERCENT",
        "30",
    )

    monkeypatch.setenv(
        "EC2_IDLE_MAXIMUM_CPU_THRESHOLD_PERCENT",
        "20",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "EC2_IDLE_AVERAGE_CPU_THRESHOLD_PERCENT "
            "cannot be greater than "
            "EC2_IDLE_MAXIMUM_CPU_THRESHOLD_PERCENT"
        ),
    ):
        (
            handler_module
            ._load_ec2_idle_configuration()
        )


def test_ec2_idle_configuration_rejects_zero_metric_coverage(
    monkeypatch,
):
    monkeypatch.setenv(
        "EC2_IDLE_MINIMUM_METRIC_COVERAGE",
        "0",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "EC2_IDLE_MINIMUM_METRIC_COVERAGE "
            "must be greater than 0.0"
        ),
    ):
        (
            handler_module
            ._load_ec2_idle_configuration()
        )