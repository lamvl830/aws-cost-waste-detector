from datetime import datetime, timezone
from typing import Any


class S3ReportPublisher:
    """
    Store generated HTML reports in a private S3 bucket and create
    temporary presigned URLs for viewing them.
    """

    def __init__(
        self,
        s3_client: Any,
        *,
        bucket_name: str,
        url_expiration_seconds: int = 86400,
    ):
        if url_expiration_seconds <= 0:
            raise ValueError(
                "url_expiration_seconds must be greater than zero"
            )

        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.url_expiration_seconds = url_expiration_seconds

    def publish(
        self,
        *,
        html: str,
        account_id: str,
        region: str,
        generated_at: datetime | None = None,
    ) -> dict[str, str]:
        """
        Upload an HTML report and return its S3 key and private URL.
        """
        if generated_at is None:
            generated_at = datetime.now(
                timezone.utc
            )

        timestamp = (
            generated_at
            .astimezone(timezone.utc)
            .strftime("%Y%m%dT%H%M%SZ")
        )

        key = (
            f"reports/{account_id}/{region}/"
            f"cost-waste-report-{timestamp}.html"
        )

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )

        url = self.s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": key,
            },
            ExpiresIn=self.url_expiration_seconds,
        )

        return {
            "bucket": self.bucket_name,
            "key": key,
            "url": url,
        }