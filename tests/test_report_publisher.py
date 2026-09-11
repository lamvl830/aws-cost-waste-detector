from datetime import datetime, timezone

import pytest

from aws_cost_waste_detector.report_publisher import (
    S3ReportPublisher,
)


class FakeS3Client:
    def __init__(self):
        self.put_object_calls = []
        self.presigned_url_calls = []

    def put_object(
        self,
        **kwargs,
    ):
        self.put_object_calls.append(
            kwargs
        )

    def generate_presigned_url(
        self,
        client_method,
        *,
        Params,
        ExpiresIn,
    ):
        self.presigned_url_calls.append(
            {
                "client_method": client_method,
                "Params": Params,
                "ExpiresIn": ExpiresIn,
            }
        )

        return (
            "https://example.com/"
            "private-report"
        )


def test_report_publisher_uploads_html():
    client = FakeS3Client()

    publisher = S3ReportPublisher(
        client,
        bucket_name="test-report-bucket",
    )

    result = publisher.publish(
        html="<html>report</html>",
        account_id="123456789012",
        region="us-east-1",
        generated_at=datetime(
            2026,
            9,
            11,
            12,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert len(
        client.put_object_calls
    ) == 1

    call = client.put_object_calls[0]

    assert call["Bucket"] == "test-report-bucket"

    assert call["Key"] == (
        "reports/123456789012/us-east-1/"
        "cost-waste-report-20260911T123000Z.html"
    )

    assert call["Body"] == (
        b"<html>report</html>"
    )

    assert call["ContentType"] == (
        "text/html; charset=utf-8"
    )

    assert result["bucket"] == (
        "test-report-bucket"
    )

    assert result["key"] == call["Key"]


def test_report_publisher_creates_presigned_url():
    client = FakeS3Client()

    publisher = S3ReportPublisher(
        client,
        bucket_name="test-report-bucket",
        url_expiration_seconds=3600,
    )

    result = publisher.publish(
        html="<html></html>",
        account_id="123456789012",
        region="us-east-1",
    )

    assert len(
        client.presigned_url_calls
    ) == 1

    call = client.presigned_url_calls[0]

    assert call["client_method"] == (
        "get_object"
    )

    assert call["Params"]["Bucket"] == (
        "test-report-bucket"
    )

    assert call["Params"]["Key"] == (
        result["key"]
    )

    assert call["ExpiresIn"] == 3600

    assert result["url"] == (
        "https://example.com/"
        "private-report"
    )


def test_report_publisher_uses_default_expiration():
    client = FakeS3Client()

    publisher = S3ReportPublisher(
        client,
        bucket_name="test-report-bucket",
    )

    publisher.publish(
        html="<html></html>",
        account_id="123456789012",
        region="us-east-1",
    )

    call = client.presigned_url_calls[0]

    # Default report links remain valid for 24 hours.
    assert call["ExpiresIn"] == 86400


def test_report_publisher_rejects_invalid_expiration():
    client = FakeS3Client()

    with pytest.raises(
        ValueError,
        match=(
            "url_expiration_seconds "
            "must be greater than zero"
        ),
    ):
        S3ReportPublisher(
            client,
            bucket_name="test-report-bucket",
            url_expiration_seconds=0,
        )