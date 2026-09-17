# Installation Guide

This guide covers deploying AWS Cost Waste Detector into your own AWS
account with Terraform.

For a product overview and feature list, see the main
[README](../README.md).

For system design details, see
[ARCHITECTURE.md](ARCHITECTURE.md).

## Deployment Model

The detector is self-hosted.

Terraform creates the detector infrastructure inside your AWS account.

One AWS region acts as the deployment or home region for:

- AWS Lambda
- Amazon DynamoDB
- Amazon S3
- Amazon SNS
- Amazon EventBridge Scheduler
- Amazon CloudWatch

The Lambda can scan supported AWS resources across multiple configured
AWS regions.

For example:

```text
Infrastructure: us-east-1

Scan regions:
- us-east-1
- us-east-2
- us-west-2
```

No detector infrastructure needs to be duplicated in each scan region.

## Prerequisites

Install:

- Terraform 1.5 or newer
- AWS CLI v2
- Git

You also need AWS credentials with permission to create the resources
defined by the Terraform configuration.

Python is not required to deploy the detector.

Python 3.11 or newer is required only for local development and tests.

## 1. Clone the Repository

```bash
git clone https://github.com/lamvl830/aws-cost-waste-detector.git
cd aws-cost-waste-detector
```

## 2. Authenticate to AWS

Configure the AWS CLI using your normal AWS authentication workflow.

Do not create or use root-user access keys for this project.

Verify the AWS account and identity Terraform will use:

```bash
aws sts get-caller-identity
```

Review the returned account ID before continuing.

If you use a named AWS CLI profile, you can either configure Terraform
through your normal environment or set the profile before running
Terraform.

PowerShell example:

```powershell
$env:AWS_PROFILE = "your-profile"
```

macOS/Linux example:

```bash
export AWS_PROFILE="your-profile"
```

Verify again:

```bash
aws sts get-caller-identity
```

## 3. Create the Terraform Configuration

Move into the infrastructure directory:

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

`terraform.tfvars` is intentionally ignored by Git.

Do not commit deployment-specific values such as notification email
addresses.

## 4. Configure the Deployment

Edit:

```text
infrastructure/terraform.tfvars
```

A typical configuration looks like:

```hcl
# Region where detector infrastructure is deployed.
aws_region = "us-east-1"

# Regions whose supported resources should be scanned.
scan_regions = [
  "us-east-1",
  "us-east-2",
]

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

### `aws_region`

`aws_region` is the detector's deployment region.

Lambda, DynamoDB, S3, SNS, EventBridge Scheduler, and CloudWatch
resources are created there.

Example:

```hcl
aws_region = "us-east-1"
```

### `scan_regions`

`scan_regions` controls where supported AWS resources are inspected.

Example:

```hcl
scan_regions = [
  "us-east-1",
  "us-east-2",
  "us-west-2",
]
```

The detector infrastructure remains in `aws_region`.

If `scan_regions` is omitted, only `aws_region` is scanned.

### `environment`

Supported values are:

```text
dev
staging
prod
```

Example:

```hcl
environment = "prod"
```

### `scan_schedule`

The default schedule is:

```hcl
scan_schedule = "rate(1 day)"
```

This value is passed to Amazon EventBridge Scheduler.

### `finding_grace_period_days`

Controls how long a waste condition must persist before progressing from
an observation toward an open finding.

Example:

```hcl
finding_grace_period_days = 7
```

### `alert_email`

Configure an email address if SNS email notifications are desired:

```hcl
alert_email = "you@example.com"
```

Set it to `null` if no email subscription should be created:

```hcl
alert_email = null
```

### Report Retention

Generated reports are automatically expired according to:

```hcl
report_retention_days = 30
```

### DynamoDB Protection

Point-in-time recovery is enabled by default:

```hcl
dynamodb_point_in_time_recovery_enabled = true
```

Deletion protection can optionally be enabled:

```hcl
dynamodb_deletion_protection_enabled = true
```

If deletion protection is enabled, it must be disabled before Terraform
can destroy the table.

## 5. Initialize Terraform

Run:

```bash
terraform init
```

## 6. Format and Validate

Run:

```bash
terraform fmt
terraform validate
```

Terraform should report that the configuration is valid.

## 7. Review the Plan

Run:

```bash
terraform plan
```

Review the output carefully.

Pay particular attention to:

- AWS account and region
- Resources being created
- Resources being replaced or destroyed
- IAM permissions
- SNS subscription configuration
- S3 and DynamoDB settings

Do not apply an unexpected destructive plan.

## 8. Deploy

Run:

```bash
terraform apply
```

Review the plan shown by Terraform and confirm when prompted.

After the apply completes, Terraform displays outputs for the deployed
resources.

You can view them again with:

```bash
terraform output
```

Useful outputs include:

- Deployment region
- Scan regions
- Lambda function name
- Lambda ARN
- DynamoDB table name
- SNS topic ARN
- EventBridge Scheduler name
- CloudWatch log group
- Report bucket name

## 9. Confirm the SNS Email Subscription

If `alert_email` is configured, AWS sends an SNS subscription
confirmation email.

Open the email and confirm the subscription.

Until the subscription is confirmed, SNS email notifications will not
be delivered.

## 10. Verify the Deployment

First confirm Terraform and AWS are synchronized:

```bash
terraform plan
```

A fully applied deployment should report:

```text
No changes. Your infrastructure matches the configuration.
```

## 11. Invoke the Detector Manually

You do not need to wait for the scheduled EventBridge invocation.

### PowerShell

From the `infrastructure` directory:

```powershell
$FUNCTION_NAME = terraform output -raw lambda_function_name
$REGION = terraform output -raw aws_region
```

Invoke the Lambda:

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

### macOS/Linux

```bash
FUNCTION_NAME=$(terraform output -raw lambda_function_name)
REGION=$(terraform output -raw aws_region)
```

Invoke:

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

## 12. Verify Multi-Region Scanning

For a configuration such as:

```hcl
aws_region = "us-east-1"

scan_regions = [
  "us-east-1",
  "us-east-2",
]
```

a successful response should include:

```json
{
  "region": "us-east-1",
  "scan_regions": [
    "us-east-1",
    "us-east-2"
  ]
}
```

`region` identifies the detector deployment region.

`scan_regions` identifies the regions whose supported resources were
evaluated.

## 13. Check CloudWatch Logs

Retrieve the log group:

```bash
terraform output -raw cloudwatch_log_group_name
```

Or tail the default project log group directly:

```bash
aws logs tail "/aws/lambda/aws-cost-waste-detector" \
  --since 10m \
  --region us-east-1
```

For multi-region runs, logs should contain entries similar to:

```text
Scanning AWS region: us-east-1
Scanning AWS region: us-east-2
Scanned AWS regions: ['us-east-1', 'us-east-2']
```

Use the actual deployment region if it differs from `us-east-1`.

## 14. View the HTML Report

Each scan generates a private HTML report in S3.

The Lambda response contains report metadata similar to:

```json
{
  "report": {
    "bucket": "example-report-bucket",
    "key": "reports/123456789012/multi-region/cost-waste-report-example.html",
    "url": "https://example-presigned-url"
  }
}
```

The URL is a temporary presigned S3 URL.

PowerShell:

```powershell
$response = Get-Content lambda-response.json | ConvertFrom-Json
Start-Process $response.report.url
```

Do not publish, commit, or permanently store presigned report URLs.

## Automatic Execution

After deployment, no local process needs to remain running.

Amazon EventBridge Scheduler invokes the Lambda according to
`scan_schedule`.

One scheduled Lambda invocation scans every configured region and
produces one consolidated report.

## Updating the Deployment

After modifying Terraform configuration or detector code:

```bash
terraform fmt
terraform validate
terraform plan
```

Review the plan.

If correct:

```bash
terraform apply
```

For detector application changes, Terraform rebuilds the Lambda package
and updates the function.

## Local Development

From the repository root, create a virtual environment.

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

Run the test suite before submitting changes:

```bash
pytest
```

## Uninstall

From the `infrastructure` directory:

```bash
terraform plan -destroy
```

Review the destruction plan carefully.

Then:

```bash
terraform destroy
```

If DynamoDB deletion protection is enabled:

```hcl
dynamodb_deletion_protection_enabled = true
```

first change it to:

```hcl
dynamodb_deletion_protection_enabled = false
```

Apply that change:

```bash
terraform apply
```

Then run:

```bash
terraform destroy
```

## Troubleshooting

### AWS Authentication Errors

Verify your active identity:

```bash
aws sts get-caller-identity
```

If using a named profile, verify that Terraform and AWS CLI commands are
using the intended profile.

### Terraform Shows Unexpected Changes

Do not apply immediately.

Check:

- Current AWS profile
- `aws_region`
- `environment`
- Resource names
- `terraform.tfvars`
- Whether you are in the expected Terraform working directory

### SNS Emails Are Not Arriving

Check whether the SNS subscription confirmation email was accepted.

Unconfirmed subscriptions do not receive notifications.

Also note that empty detector scans do not send report summary emails.

### Lambda Invocation Fails in One Scan Region

The current multi-region implementation treats a regional failure as a
failure of the overall Lambda invocation.

Check CloudWatch logs to identify which region failed and which AWS API
returned the error.

### Report URL No Longer Works

Presigned report URLs expire.

Run the detector again to generate a new report and temporary URL.

### No Findings Are Returned

Zero findings can be a valid result.

The detector only reports resources that match currently implemented
waste rules.

A zero-finding scan still produces an HTML report.