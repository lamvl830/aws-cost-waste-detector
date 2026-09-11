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

AWS provides powerful cost-management tools, but teams can still miss
resource-level waste between billing reviews.

AWS Cost Waste Detector complements those services by:

- Scanning actual AWS resources on a schedule
- Tracking findings across scans instead of reporting one-time observations
- Waiting for waste conditions to persist before prioritizing them
- Ranking findings by estimated savings, severity, and age
- Sending alerts when high-priority waste is detected
- Generating private, account-local reports without sending AWS credentials
  or resource data to an external service

Current examples include:

- EBS volumes left unattached after EC2 instances are terminated
- Elastic IP addresses that remain allocated but unused
- Resources that continue generating avoidable costs over time

This project is not intended to replace AWS Cost Optimization Hub,
Trusted Advisor, Compute Optimizer, or Cost Explorer. It provides a
focused, self-hosted workflow for turning specific resource conditions
into persistent findings and actionable alerts.

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

For some EBS volume types, additional IOPS or throughput charges may not
be included in the current estimate.

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
- Resource type
- Resource IDs
- Finding age
- Recommendations
- AWS Console links

Reports are stored in a private S3 bucket.

Public access is blocked, encryption at rest is enabled, and reports are
automatically deleted after the configured retention period.

A temporary presigned URL is generated for private report access.

## Notifications

Amazon SNS is used for notifications.

### Finding Alerts

HIGH and CRITICAL findings can trigger immediate notifications.

The detector records when a finding was successfully notified so the
same finding is not repeatedly emailed on every scan.

### Report Notifications

When a scan contains findings, the detector sends a consolidated summary
containing estimated savings and a private report link.

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

See the full [Security Model](docs/SECURITY.md).

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

For a deeper explanation, see the
[Architecture documentation](docs/ARCHITECTURE.md).

## Installation

### Prerequisites

You need:

- Terraform 1.5+
- AWS CLI v2
- Git
- AWS credentials with permission to deploy the Terraform resources

Python is only required if you want to run the test suite or develop the
project locally.

### 1. Clone the repository

```bash
git clone https://github.com/lamvl830/aws-cost-waste-detector.git
cd aws-cost-waste-detector
```

### 2. Verify AWS authentication

Before deploying, confirm which AWS account your credentials point to:

```bash
aws sts get-caller-identity
```

The returned account should be the AWS account where you want the
detector installed.

If you use a named AWS CLI profile, configure that profile through your
normal AWS CLI credential workflow before running Terraform.

### 3. Create your deployment configuration

Move into the Terraform directory:

```bash
cd infrastructure
```

Copy the example configuration.

PowerShell:

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
```

macOS/Linux:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` for your AWS account and preferences.

Example:

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

`terraform.tfvars` is intentionally ignored by Git so deployment-specific
values such as email addresses are not committed to the repository.

### 4. Initialize Terraform

```bash
terraform init
```

### 5. Validate and review the deployment

```bash
terraform validate
terraform plan
```

Review the Terraform plan before continuing.

### 6. Deploy

```bash
terraform apply
```

Review the plan again and confirm the deployment when prompted.

After deployment, Terraform displays useful outputs including:

- AWS region
- Lambda function name
- Lambda ARN
- DynamoDB table name
- SNS topic ARN
- EventBridge Scheduler name
- CloudWatch log group
- S3 report bucket name

You can display them again with:

```bash
terraform output
```

### 7. Confirm the SNS subscription

If `alert_email` is configured, Amazon SNS sends a subscription
confirmation email.

Open that email and confirm the subscription.

Notifications are not delivered until the subscription is confirmed.

For a more detailed walkthrough, see the
[Installation Guide](docs/INSTALL.md).

## Quick Start

After deployment, the detector runs automatically according to
`scan_schedule`.

You can also run it manually at any time.

### PowerShell

From the `infrastructure` directory, retrieve the deployed Lambda name
and AWS region:

```powershell
$FUNCTION_NAME = terraform output -raw lambda_function_name
$REGION = terraform output -raw aws_region
```

Invoke the detector:

```powershell
aws lambda invoke `
  --function-name $FUNCTION_NAME `
  --payload '{}' `
  --cli-binary-format raw-in-base64-out `
  --region $REGION `
  --no-cli-pager `
  lambda-response.json
```

View the response:

```powershell
Get-Content lambda-response.json
```

Open the generated HTML report directly in your default browser:

```powershell
$response = Get-Content lambda-response.json | ConvertFrom-Json
Start-Process $response.report.url
```

### macOS / Linux

Retrieve the deployed Lambda name and AWS region:

```bash
FUNCTION_NAME=$(terraform output -raw lambda_function_name)
REGION=$(terraform output -raw aws_region)
```

Invoke the detector:

```bash
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  --region "$REGION" \
  lambda-response.json
```

View the response:

```bash
cat lambda-response.json
```

A successful invocation returns information similar to:

```json
{
  "account_id": "123456789012",
  "region": "us-east-1",
  "total_findings": 0,
  "resolved_findings": 0,
  "notifications_sent": 0,
  "report_notification_message_id": null,
  "report": {
    "bucket": "example-report-bucket",
    "key": "reports/123456789012/us-east-1/cost-waste-report-example.html",
    "url": "https://example-presigned-url"
  },
  "summary": {
    "total_findings": 0,
    "total_monthly_savings": 0,
    "total_annual_savings": 0,
    "top_opportunities": []
  }
}
```

The detector will:

1. Scan supported AWS resources.
2. Estimate potential savings.
3. Store or update findings in DynamoDB.
4. Reconcile findings that disappeared since the previous scan.
5. Rank current findings.
6. Send eligible notifications.
7. Generate a private HTML report in S3.

After deployment, no long-running local process is required. The detector
runs inside your AWS account through AWS Lambda and EventBridge
Scheduler.

## Viewing Reports

Every scan generates a private HTML report in the detector's S3 bucket.

When findings exist, the SNS summary notification includes a temporary
presigned URL to the report.

You can find the report bucket with:

```bash
terraform output -raw report_bucket_name
```

Reports are private and are not publicly accessible.

By default, generated reports are retained for 30 days. This can be
changed using:

```hcl
report_retention_days = 30
```

Presigned report links are temporary. Treat them as temporary credentials
and do not publish or commit them.

## Configuration

Common configuration options include:

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

```text
infrastructure/terraform.tfvars.example
```

for all supported configuration values.

## Automatic Scans

By default, the detector runs once per day:

```hcl
scan_schedule = "rate(1 day)"
```

Amazon EventBridge Scheduler invokes the detector Lambda automatically.

The schedule can be changed through `terraform.tfvars`.

## DynamoDB Finding History

The detector stores findings in DynamoDB using a resource/rule identity:

```text
PK = RESOURCE#{resource_arn}
SK = RULE#{rule_id}
```

This allows one AWS resource to have multiple independent cost-waste
findings while preserving lifecycle history across scans.

Point-in-time recovery is enabled by default.

## Testing

For local development, Python 3.11 or newer is required.

Create and activate a virtual environment, then install the project with
development dependencies.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

The project also runs its test suite automatically using GitHub Actions
for pull requests and changes to `main`.

## Project Structure

```text
aws-cost-waste-detector/
├── docs/            # Architecture, installation, and security docs
├── infrastructure/  # Terraform deployment
├── src/             # Detector application code
├── tests/           # Automated tests
├── pyproject.toml
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

If DynamoDB deletion protection was enabled:

```hcl
dynamodb_deletion_protection_enabled = true
```

set it back to:

```hcl
dynamodb_deletion_protection_enabled = false
```

apply that change first, and then run `terraform destroy`.

## Documentation

Additional documentation:

- [Installation Guide](docs/INSTALL.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security Model](docs/SECURITY.md)

## Disclaimer

AWS Cost Waste Detector provides cost optimization recommendations and
estimated savings.

Actual AWS billing may differ from the estimates shown by the detector.

The detector does not automatically modify or delete customer resources.

Always review a finding before taking remediation action.