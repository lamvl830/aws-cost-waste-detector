from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Finding:
    rule_id: str
    account_id: str
    region: str
    resource_arn: str
    resource_id: str
    resource_type: str
    title: str
    description: str
    severity: str
    recommendation: str
    estimated_monthly_savings: Decimal | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.estimated_monthly_savings is not None:
            value["estimated_monthly_savings"] = str(self.estimated_monthly_savings)
        return value
