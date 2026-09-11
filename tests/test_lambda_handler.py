from aws_cost_waste_detector import lambda_handler as handler_module


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
    ):
        calls["session"] = session
        calls["region"] = region
        calls["table_name"] = table_name

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

    assert result["account_id"] == "123456789012"
    assert result["total_findings"] == 1
    assert result["resolved_findings"] == 0


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