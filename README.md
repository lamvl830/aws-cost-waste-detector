# AWS Cost Waste Detector

A production-oriented FinOps platform that ingests AWS cost-optimization recommendations,
enriches them with resource and ownership context, prioritizes opportunities, and eventually
supports approval-based remediation.

## v0.1 milestone

The first milestone runs locally and detects EBS volumes that are currently unattached.
It intentionally does not claim they have been unattached for N days because EC2's
DescribeVolumes API does not expose the detachment timestamp. A later persistence layer will
track first_seen/last_seen and promote findings after a grace period.

## Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Configure AWS credentials using your preferred AWS CLI profile, then run:

```powershell
python -m aws_cost_waste_detector.main --profile YOUR_PROFILE --region us-east-1
```

Or use your default profile:

```powershell
python -m aws_cost_waste_detector.main --region us-east-1
```

Run tests:

```powershell
pytest
```

## Read-only permissions needed for v0.1

- `sts:GetCallerIdentity`
- `ec2:DescribeVolumes`
