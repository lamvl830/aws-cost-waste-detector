import aws_cost_waste_detector.detector as detector_module


class FakeStsClient:
    def get_caller_identity(self):
        return {
            "Account": "123456789012",
            "Arn": (
                "arn:aws:iam::123456789012:"
                "user/test-user"
            ),
        }


class FakeDynamoTable:
    pass


class FakeDynamoResource:
    def __init__(self):
        self.table = FakeDynamoTable()

    def Table(self, table_name):
        assert table_name == "WasteFindings"
        return self.table


class FakeSession:
    def __init__(self):
        self.client_calls = []
        self.resource_calls = []
        self.dynamodb = FakeDynamoResource()

    def client(
        self,
        service_name,
        *,
        region_name=None,
    ):
        self.client_calls.append(
            {
                "service_name": service_name,
                "region_name": region_name,
            }
        )

        if service_name == "sts":
            return FakeStsClient()

        # The detector only needs opaque fake clients here because the
        # individual scanners are mocked below.
        return {
            "service_name": service_name,
            "region_name": region_name,
        }

    def resource(
        self,
        service_name,
        *,
        region_name=None,
    ):
        self.resource_calls.append(
            {
                "service_name": service_name,
                "region_name": region_name,
            }
        )

        assert service_name == "dynamodb"

        return self.dynamodb


class FakeFinding:
    def __init__(self):
        self.resource_id = "i-idle"
        self.rule_id = "EC2_IDLE"
        self.resource_arn = (
            "arn:aws:ec2:us-east-2:"
            "123456789012:"
            "instance/i-idle"
        )

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "resource_id": self.resource_id,
            "resource_arn": self.resource_arn,
            "resource_type": "AWS::EC2::Instance",
            "account_id": "123456789012",
            "region": "us-east-2",
            "title": "EC2 instance appears idle",
            "severity": "MEDIUM",
            "recommendation": (
                "Review the instance workload."
            ),
            "estimated_monthly_savings": 70.08,
            "metadata": {},
        }


def test_run_detector_includes_idle_ec2_scan(
    monkeypatch,
):
    session = FakeSession()
    finding = FakeFinding()

    captured = {}

    # Keep the test focused on detector orchestration rather than the
    # behavior of the individual EBS/EIP scanners.
    monkeypatch.setattr(
        detector_module,
        "scan_unattached_ebs",
        lambda *args, **kwargs: iter([]),
    )

    monkeypatch.setattr(
        detector_module,
        "scan_unused_eips",
        lambda *args, **kwargs: iter([]),
    )

    def fake_scan_idle_ec2(
        ec2_client,
        cloudwatch_client,
        *,
        account_id,
        region,
        partition,
        price_provider,
        lookback_days,
        thresholds,
    ):
        captured["ec2_client"] = (
            ec2_client
        )
        captured["cloudwatch_client"] = (
            cloudwatch_client
        )
        captured["account_id"] = account_id
        captured["region"] = region
        captured["partition"] = partition
        captured["price_provider"] = (
            price_provider
        )
        captured["lookback_days"] = lookback_days
        captured["thresholds"] = thresholds

        return iter(
            [finding]
        )

    monkeypatch.setattr(
        detector_module,
        "scan_idle_ec2",
        fake_scan_idle_ec2,
    )

    monkeypatch.setattr(
        detector_module,
        "list_active_findings",
        lambda *args, **kwargs: [],
    )

    saved_findings = []

    def fake_save_finding(
        table,
        saved_finding,
        *,
        grace_period_days,
    ):
        saved_findings.append(
            saved_finding
        )

        assert grace_period_days == 7

        return "OBSERVED"

    monkeypatch.setattr(
        detector_module,
        "save_finding",
        fake_save_finding,
    )

    monkeypatch.setattr(
        detector_module,
        "finding_key",
        lambda finding: {
            "PK": (
                f"RESOURCE#"
                f"{finding.resource_arn}"
            ),
            "SK": (
                f"RULE#{finding.rule_id}"
            ),
        },
    )

    monkeypatch.setattr(
        detector_module,
        "calculate_current_finding_priority",
        lambda *args, **kwargs: {
            "age_days": 0,
            "priority_score": 25,
            "priority_label": "LOW",
        },
    )

    def fake_find_missing_items(
        current_findings,
        stored_findings,
        *,
        reconciled_rule_ids,
    ):
        captured["reconciled_rule_ids"] = (
            set(reconciled_rule_ids)
        )

        return []

    monkeypatch.setattr(
        detector_module,
        "find_missing_items",
        fake_find_missing_items,
    )

    monkeypatch.setattr(
        detector_module,
        "build_cost_summary",
        lambda findings: {
            "total_findings": len(
                findings
            ),
            "total_monthly_savings": 70.08,
            "total_annual_savings": 840.96,
            "top_opportunities": findings,
        },
    )

    # Pricing providers are not under test here. Replacing them keeps this
    # test focused entirely on detector orchestration.
    monkeypatch.setattr(
        detector_module,
        "AwsEbsPriceProvider",
        lambda client: object(),
    )

    monkeypatch.setattr(
        detector_module,
        "AwsEipPriceProvider",
        lambda client: object(),
    )

    monkeypatch.setattr(
        detector_module,
        "Ec2OnDemandPriceProvider",
        lambda client: object(),
    )

    result = detector_module.run_detector(
        session,
        region="us-east-2",
        storage_region="us-east-1",
    )

    assert captured["account_id"] == (
        "123456789012"
    )

    assert captured["region"] == (
        "us-east-2"
    )

    assert captured["partition"] == (
        "aws"
    )

    assert captured["ec2_client"] == {
        "service_name": "ec2",
        "region_name": "us-east-2",
    }

    assert captured[
        "cloudwatch_client"
    ] == {
        "service_name": "cloudwatch",
        "region_name": "us-east-2",
    }

    assert captured["lookback_days"] == 7
    
    assert captured["thresholds"] is None

    assert saved_findings == [
        finding
    ]

    assert (
        "EC2_IDLE"
        in captured[
            "reconciled_rule_ids"
        ]
    )

    assert (
        "EBS_CURRENTLY_UNATTACHED"
        in captured[
            "reconciled_rule_ids"
        ]
    )

    assert (
        "EIP_UNUSED"
        in captured[
            "reconciled_rule_ids"
        ]
    )

    assert (
        result["findings"][0][
            "rule_id"
        ]
        == "EC2_IDLE"
    )

    assert (
        result["findings"][0][
            "resource_id"
        ]
        == "i-idle"
    )

    assert (
        result["summary"][
            "total_findings"
        ]
        == 1
    )

    # Resource APIs should use the scan region.
    assert {
        "service_name": "cloudwatch",
        "region_name": "us-east-2",
    } in session.client_calls

    # Detector state should remain in the deployment/storage region.
    assert {
        "service_name": "dynamodb",
        "region_name": "us-east-1",
    } in session.resource_calls