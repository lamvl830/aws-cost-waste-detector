from aws_cost_waste_detector.scanners.eip import scan_unused_eips


class FakeEC2Client:
    def __init__(self, addresses):
        self.addresses = addresses

    def describe_addresses(self):
        return {"Addresses": self.addresses}


def test_unused_eip_becomes_finding():
    client = FakeEC2Client(
        [
            {
                "PublicIp": "203.0.113.10",
                "AllocationId": "eipalloc-123",
                "Domain": "vpc",
                "Tags": [
                    {"Key": "Name", "Value": "old-eip"},
                ],
            }
        ]
    )

    findings = list(
        scan_unused_eips(
            client,
            account_id="123456789012",
            region="us-east-1",
        )
    )

    assert len(findings) == 1
    assert findings[0].rule_id == "EIP_UNUSED"
    assert findings[0].resource_id == "eipalloc-123"


def test_associated_eip_is_ignored():
    client = FakeEC2Client(
        [
            {
                "PublicIp": "203.0.113.20",
                "AllocationId": "eipalloc-456",
                "AssociationId": "eipassoc-789",
                "Domain": "vpc",
            }
        ]
    )

    findings = list(
        scan_unused_eips(
            client,
            account_id="123456789012",
            region="us-east-1",
        )
    )

    assert findings == []


def test_ignore_tag_suppresses_eip():
    client = FakeEC2Client(
        [
            {
                "PublicIp": "203.0.113.30",
                "AllocationId": "eipalloc-999",
                "Domain": "vpc",
                "Tags": [
                    {"Key": "WasteDetectorIgnore", "Value": "true"},
                ],
            }
        ]
    )

    findings = list(
        scan_unused_eips(
            client,
            account_id="123456789012",
            region="us-east-1",
        )
    )

    assert findings == []
