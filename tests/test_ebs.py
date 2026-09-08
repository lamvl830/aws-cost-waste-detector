from aws_cost_waste_detector.scanners.ebs import scan_unattached_ebs


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages
        self.received_kwargs = None

    def paginate(self, **kwargs):
        self.received_kwargs = kwargs
        yield from self.pages


class FakeEC2Client:
    def __init__(self, pages):
        self.paginator = FakePaginator(pages)

    def get_paginator(self, operation_name):
        assert operation_name == "describe_volumes"
        return self.paginator


def test_returns_unattached_volume_finding():
    client = FakeEC2Client(
        [
            {
                "Volumes": [
                    {
                        "VolumeId": "vol-123",
                        "Size": 100,
                        "VolumeType": "gp3",
                        "AvailabilityZone": "us-east-1a",
                        "Encrypted": True,
                        "Tags": [{"Key": "Name", "Value": "old-data"}],
                    }
                ]
            }
        ]
    )

    findings = list(
        scan_unattached_ebs(
            client,
            account_id="123456789012",
            region="us-east-1",
        )
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "EBS_CURRENTLY_UNATTACHED"
    assert finding.resource_id == "vol-123"
    assert finding.metadata["size_gib"] == 100
    assert finding.metadata["name"] == "old-data"
    assert finding.resource_arn == (
        "arn:aws:ec2:us-east-1:123456789012:volume/vol-123"
    )


def test_ignores_opted_out_volume():
    client = FakeEC2Client(
        [
            {
                "Volumes": [
                    {
                        "VolumeId": "vol-ignore",
                        "Size": 50,
                        "Tags": [
                            {"Key": "WasteDetectorIgnore", "Value": "true"}
                        ],
                    }
                ]
            }
        ]
    )

    findings = list(
        scan_unattached_ebs(
            client,
            account_id="123456789012",
            region="us-east-1",
        )
    )

    assert findings == []
