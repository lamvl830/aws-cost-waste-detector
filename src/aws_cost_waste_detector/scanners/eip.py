from collections.abc import Iterable
from typing import Any

from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.cost.eip import estimate_eip_monthly_cost
from aws_cost_waste_detector.pricing.eip import EipPriceProvider

IGNORE_TAG = "WasteDetectorIgnore"

def _tags_to_dict(tags: list[dict[str, str]] | None) -> dict[str, str]:
    return {tag["Key"]: tag["Value"] for tag in (tags or [])}


def _ignored(tags: dict[str, str]) -> bool:
    return tags.get(IGNORE_TAG, "").strip().lower() in {"1", "true", "yes"}


def scan_unused_eips(
    ec2_client: Any,
    *,
    account_id: str,
    region: str,
    partition: str = "aws",
    price_provider: EipPriceProvider | None = None,
) -> Iterable[Finding]:
    response = ec2_client.describe_addresses()

    for address in response.get("Addresses", []):
        tags = _tags_to_dict(address.get("Tags"))

        if _ignored(tags):
            continue

        # If there is an AssociationId, the Elastic IP is currently in use.
        if address.get("AssociationId"):
            continue

        allocation_id = address.get("AllocationId")
        public_ip = address.get("PublicIp")

        # AllocationId exists for VPC Elastic IPs.
        resource_id = allocation_id or public_ip

        estimated_monthly_savings = None

        if price_provider is not None:
            hourly_price = price_provider.get_hourly_price(
                region=region,
            )

            estimated_monthly_savings = estimate_eip_monthly_cost(
                hourly_price=hourly_price,
            )

        yield Finding(
            rule_id="EIP_UNUSED",
            account_id=account_id,
            region=region,
            resource_arn=(
                f"arn:{partition}:ec2:{region}:{account_id}:elastic-ip/{resource_id}"
            ),
            resource_id=resource_id,
            resource_type="AWS::EC2::EIP",
            title="Elastic IP is not associated with a resource",
            description=(
                f"Elastic IP {public_ip} is allocated but currently unassociated."
            ),
            severity="LOW",
            recommendation=(
                "Verify the Elastic IP is no longer required and release it "
                "if it is unused."
            ),
            estimated_monthly_savings=estimated_monthly_savings,
            metadata={
                "public_ip": public_ip,
                "allocation_id": allocation_id,
                "domain": address.get("Domain"),
                "tags": tags,
            },
        )