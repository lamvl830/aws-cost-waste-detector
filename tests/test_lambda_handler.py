from aws_cost_waste_detector import lambda_handler as handler_module
import pytest


class FakeSession:
    """
    Minimal fake boto3 session for Lambda handler tests.
    """

    def __init__(
        self,
        *,
        region_name: str,
    ):
        self.region_name = region_name

    def client(
        self,
        service_name: str,
        *,
        region_name: str,
    ):
        return {
            "service_name": service_name,
            "region_name": region_name,
        }

def test_lambda_handler_runs_detector(
    monkeypatch,
):
    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "WASTE_FINDINGS_TABLE",
        "TestWasteFindings",
    )

    monkeypatch.delenv(
        "COST_WASTE_ALERTS_TOPIC_ARN",
        raising=False,
    )

    # Ensure this test verifies the default grace period.
    monkeypatch.delenv(
        "FINDING_GRACE_PERIOD_DAYS",
        raising=False,
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
        table_name,
        notifier=None,
        grace_period_days=7,
    ):
        calls["session"] = session
        calls["region"] = region
        calls["table_name"] = table_name
        calls["notifier"] = notifier
        calls["grace_period_days"] = grace_period_days

        return {
            "account_id": "123456789012",
            "region": "us-east-1",
            "findings": [
                {
                    "resource_id": "vol-123",
                }
            ],
            "summary": {
                "total_findings": 1,
                "total_monthly_savings": 8.0,
                "total_annual_savings": 96.0,
                "top_opportunities": [],
            },
            "persistence_results": [],
            "resolution_results": [],
            "notification_results": [],
        }

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
    assert calls["table_name"] == "TestWasteFindings"
    assert calls["notifier"] is None
    assert calls["grace_period_days"] == 7

    assert result["account_id"] == "123456789012"
    assert result["region"] == "us-east-1"
    assert result["total_findings"] == 1
    assert result["resolved_findings"] == 0
    assert result["notifications_sent"] == 0
    assert result["report"] is None


def test_lambda_handler_requires_region(
    monkeypatch,
):
    monkeypatch.delenv(
        "AWS_REGION",
        raising=False,
    )

    try:
        handler_module.lambda_handler(
            {},
            None,
        )

        assert False, "Expected RuntimeError"

    except RuntimeError as error:
        assert (
            "AWS_REGION environment variable is not configured"
            in str(error)
        )


def test_lambda_handler_uses_configured_grace_period(
    monkeypatch,
):
    monkeypatch.setenv(
        "AWS_REGION",
        "us-east-1",
    )

    monkeypatch.setenv(
        "FINDING_GRACE_PERIOD_DAYS",
        "3",
    )

    monkeypatch.delenv(
        "COST_WASTE_ALERTS_TOPIC_ARN",
        raising=False,
    )

    monkeypatch.delenv(
        "REPORT_BUCKET",
        raising=False,
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
        table_name,
        notifier=None,
        grace_period_days=7,
    ):
        calls["grace_period_days"] = grace_period_days

        return {
            "account_id": "123456789012",
            "region": region,
            "findings": [],
            "summary": {
                "total_findings": 0,
                "total_monthly_savings": 0.0,
                "total_annual_savings": 0.0,
                "top_opportunities": [],
            },
            "persistence_results": [],
            "resolution_results": [],
            "notification_results": [],
        }

    monkeypatch.setattr(
        handler_module,
        "run_detector",
        fake_run_detector,
    )

    handler_module.lambda_handler(
        {},
        None,
    )

    assert calls["grace_period_days"] == 3


def test_lambda_handler_rejects_invalid_grace_period(
    monkeypatch,
):
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
        match="FINDING_GRACE_PERIOD_DAYS must be an integer",
    ):
        handler_module.lambda_handler(
            {},
            None,
        )


def test_lambda_handler_rejects_negative_grace_period(
    monkeypatch,
):
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
        match="FINDING_GRACE_PERIOD_DAYS cannot be negative",
    ):
        handler_module.lambda_handler(
            {},
            None,
        )


def test_lambda_handler_publishes_html_report(
    monkeypatch,
):
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

    monkeypatch.delenv(
        "COST_WASTE_ALERTS_TOPIC_ARN",
        raising=False,
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
        table_name,
        notifier=None,
        grace_period_days=7,
    ):
        return {
            "account_id": "123456789012",
            "region": "us-east-1",
            "findings": [],
            "summary": {
                "total_findings": 0,
                "total_monthly_savings": 0.0,
                "total_annual_savings": 0.0,
                "top_opportunities": [],
            },
            "persistence_results": [],
            "resolution_results": [],
            "notification_results": [],
        }

    monkeypatch.setattr(
        handler_module,
        "run_detector",
        fake_run_detector,
    )

    monkeypatch.setattr(
        handler_module,
        "render_html_report",
        lambda **kwargs: "<html>report</html>",
    )

    class FakePublisher:
        def __init__(
            self,
            s3_client,
            *,
            bucket_name,
        ):
            assert bucket_name == "test-report-bucket"

        def publish(
            self,
            *,
            html,
            account_id,
            region,
        ):
            assert html == "<html>report</html>"
            assert account_id == "123456789012"
            assert region == "us-east-1"

            return {
                "bucket": "test-report-bucket",
                "key": "reports/test.html",
                "url": "https://example.com/report",
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