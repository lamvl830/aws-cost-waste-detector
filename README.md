# AWS Cost Waste Detector

A self-hosted AWS FinOps tool that automatically identifies potentially
wasteful AWS resources, estimates their cost, tracks finding history,
prioritizes savings opportunities, and generates private HTML reports.

The detector runs entirely inside your AWS account using AWS Lambda and
Terraform.

## Current v0.1 Features

AWS Cost Waste Detector currently detects:

- Unattached Amazon EBS volumes
- Unused Elastic IP addresses

It also provides:

- Live AWS Pricing API integration
- Estimated monthly and annual savings
- Finding lifecycle tracking
- Priority scoring
- DynamoDB persistence
- HIGH and CRITICAL finding notifications
- Private HTML reports stored in Amazon S3
- Temporary presigned report URLs
- EventBridge scheduled scans
- CloudWatch logging
- Lambda error and throttling alarms
- Terraform-based deployment

## Example Workflow

```text
EventBridge Scheduler
        |
        v
   AWS Lambda
        |
        +----> Scan EBS volumes
        |
        +----> Scan Elastic IPs
        |
        +----> AWS Pricing API
        |
        v
   Build Findings
        |
        +----> DynamoDB lifecycle history
        |
        +----> Priority scoring
        |
        +----> SNS alerts
        |
        v
 Generate HTML Report
        |
        v
   Private S3 Bucket
        |
        v
 Temporary Presigned URL
```

## Why This Project?

Cloud waste is often easy to create and difficult to notice.

Examples include:

- EBS volumes left behind after EC2 instances are terminated
- Elastic IP addresses that are allocated but no longer used
- Resources that remain unused for weeks or months

AWS Cost Waste Detector continuously scans for these conditions and
turns them into prioritized, persistent findings instead of one-time
console observations.

## Finding Lifecycle

Findings progress through a simple lifecycle:

```text
OBSERVED
    |
    | condition persists beyond grace period
    v
OPEN
    |
    | resource is no longer wasteful
    v
RESOLVED
```

A resolved finding that appears again begins a new observation window.

The default grace period is 7 days and can be configured through
Terraform.

## Priority Scoring

Findings are ranked using:

- Estimated monthly savings
- Finding age
- Severity

Priority labels are:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

This helps surface the savings opportunities that are most worth
reviewing first.

## Cost Estimation

The detector retrieves live AWS pricing rather than relying only on
hardcoded prices.

Current pricing support includes:

### Amazon EBS

Storage pricing is retrieved using the AWS Pricing API and applied to
the size and volume type of unattached EBS volumes.

### Elastic IP / Public IPv4

The detector retrieves the current public IPv4 hourly price and
estimates the monthly cost using approximately 730 hours per month.

Savings values are estimates. Actual AWS billing may vary.

## HTML Reports

Every scan generates a self-contained HTML report containing:

- AWS account
- Region
- Generation timestamp
- Current findings
- Estimated monthly savings
- Estimated annual savings
- Priority
- Severity
- Resource IDs
- Finding age
- Recommendations
- AWS Console links

Reports are stored in a private S3 bucket.

Public access is blocked, encryption at rest is enabled, and reports are
automatically deleted after the configured retention period.

A temporary presigned URL is generated for report access.

## Notifications

Amazon SNS is used for notifications.

### Finding Alerts

HIGH and CRITICAL findings can trigger immediate notifications.

The detector records when a finding was successfully notified so the
same finding is not repeatedly emailed on every scan.

### Report Notifications

When a scan contains findings, the detector can send a consolidated
summary containing a private report link.

Empty scans still generate reports but do not send unnecessary report
emails.

### Detector Health Alerts

CloudWatch alarms monitor:

- Lambda execution errors
- Lambda throttling

These alarms publish to the detector SNS topic.

## Security

Version 0.1 is self-hosted.

AWS resources and finding data remain inside the customer's AWS account.

The detector does **not** require customer AWS access keys to be sent to
an external service.

The Lambda execution role can:

- Describe supported AWS resources
- Read AWS pricing
- Read and write its own DynamoDB findings
- Publish to its own SNS topic
- Read and write reports in its own S3 bucket
- Write its own CloudWatch logs

The detector does **not** receive permissions to automatically delete
EBS volumes or release Elastic IP addresses.

See:

[Security Model](docs/SECURITY.md)

## Architecture

The main AWS services used are:

```text
Amazon EventBridge Scheduler
AWS Lambda
Amazon EC2 APIs
AWS Pricing API
Amazon DynamoDB
Amazon S3
Amazon SNS
Amazon CloudWatch
AWS IAM
```

For a deeper explanation:

[Architecture](docs/ARCHITECTURE.md)

## Installation

### Prerequisites

You need:

- Terraform 1.5+
- AWS CLI v2
- Git
- AWS credentials with permission to deploy the Terraform resources

Clone the repository:

```bash
git clone https://github.com/lamvl830/aws-cost-waste-detector.git
cd aws-cost-waste-detector
```

Move into the infrastructure directory:

```bash
cd infrastructure
```

Create your local Terraform configuration.

PowerShell:

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
```

macOS/Linux:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`, then deploy:

```bash
terraform init
terraform validate
terraform plan
terraform apply
```

If an SNS email address is configured, confirm the subscription email
sent by AWS after deployment.

For the full installation guide:

[Installation Guide](docs/INSTALL.md)

## Configuration

Example configuration:

```hcl
aws_region = "us-east-1"

environment = "prod"

project_name = "aws-cost-waste-detector"

findings_table_name = "WasteFindings"

scan_schedule = "rate(1 day)"

finding_grace_period_days = 7

alert_email = "you@example.com"

report_retention_days = 30

dynamodb_point_in_time_recovery_enabled = true

dynamodb_deletion_protection_enabled = false
```

See:

`infrastructure/terraform.tfvars.example`

for all supported configuration values.

## Testing

Create and activate a Python virtual environment, install development
dependencies, and run:

```bash
pytest
```

The project also runs its test suite automatically using GitHub Actions
for pull requests and changes to `main`.

## Project Structure

```text
aws-cost-waste-detector/
├── docs/            # Architecture, install, and security docs
├── infrastructure/  # Terraform deployment
├── src/             # Detector application code
├── tests/           # Automated tests
└── README.md
```

## Current Scope

Version 0.1 currently supports:

```text
1 AWS account per deployment
1 AWS region per deployment

Waste detectors:
- Unattached EBS volumes
- Unused Elastic IP addresses
```

## Roadmap

Potential future additions include:

- Multi-region scanning
- AWS Organizations / multi-account support
- Additional waste detectors
- RDS optimization
- EC2 idle-resource detection
- Snapshot cleanup opportunities
- NAT Gateway analysis
- Load balancer analysis
- Centralized dashboard
- REST API
- Historical savings trends
- Automated remediation workflows
- Hosted SaaS deployment option

## Uninstall

From the `infrastructure` directory:

```bash
terraform destroy
```

Review the Terraform destruction plan before confirming.

If DynamoDB deletion protection was enabled, disable it and apply the
configuration before destroying the deployment.

## Disclaimer

AWS Cost Waste Detector provides cost optimization recommendations and
estimated savings.

It does not automatically modify or delete customer resources.

Always review a finding before taking remediation action.