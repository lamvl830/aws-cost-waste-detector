# Security Model

AWS Cost Waste Detector is designed as a self-hosted, read-oriented
FinOps scanner.

The detector runs inside the customer's AWS account and does not require
customer AWS credentials to be sent to an external application service.

This document describes the security boundaries and permissions of the
current architecture.

For deployment instructions, see [INSTALL.md](INSTALL.md).

For system design details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Security Principles

The current design follows several principles:

- Keep detector infrastructure inside the customer's AWS account
- Use IAM roles instead of embedding AWS credentials in application code
- Use read-only permissions for customer workloads where practical
- Limit write access to detector-owned resources
- Keep reports private
- Encrypt detector storage at rest
- Avoid automatic remediation or deletion of customer resources
- Fail safe when utilization telemetry is incomplete
- Surface detector execution failures through CloudWatch

## Trust Boundary

The primary trust boundary is the customer's AWS account.

```text
Customer AWS Account
        |
        +--> Detector Lambda
        |
        +--> Detector DynamoDB table
        |
        +--> Detector S3 report bucket
        |
        +--> Detector SNS topic
        |
        +--> Detector CloudWatch logs and metrics
        |
        +--> Supported customer AWS resources
```

The detector does not require a separately hosted control plane to
access customer resources.

## AWS Credentials

The deployed Lambda uses an IAM execution role.

No static AWS access keys are stored in the Lambda package.

Customers deploying with Terraform use their own AWS authentication
workflow.

Root-user access keys should not be used to deploy or operate the
detector.

Local credential files, environment variables, or named AWS CLI profiles
used during deployment are not packaged into the Lambda function.

## IAM Permissions

The Lambda execution role is divided conceptually into two categories.

### Customer Resource Permissions

The detector needs read access to supported resources and utilization
telemetry.

Current resource-observation permissions include:

```text
ec2:DescribeVolumes
ec2:DescribeAddresses
ec2:DescribeInstances
cloudwatch:GetMetricData
pricing:GetProducts
```

These actions allow the detector to discover supported resources,
retrieve EC2 utilization metrics, and estimate cost.

They do not modify the resources being inspected.

Some EC2 `Describe` operations and CloudWatch metric-read operations do
not support useful resource-level IAM scoping for this access pattern,
so the IAM resource is:

```text
*
```

This wildcard permits read-oriented discovery and metric access. It does
not grant EC2 modification permissions.

The role does not receive permissions such as:

```text
ec2:DeleteVolume
ec2:ReleaseAddress
ec2:StopInstances
ec2:TerminateInstances
```

### Detector-Owned Resource Permissions

The Lambda can write to resources that belong to the detector itself.

These include:

- Detector DynamoDB table
- Detector S3 report bucket
- Detector SNS topic
- Detector CloudWatch log group

Where supported, Terraform restricts these permissions to the specific
resources created for the deployment.

## Idle EC2 Security Model

Idle EC2 detection is advisory and read-only.

For each eligible running On-Demand instance, the detector can read:

- Instance identity and configuration metadata
- Instance type
- Launch time
- Platform details
- Tenancy
- CPU utilization from CloudWatch
- NetworkIn and NetworkOut metrics from CloudWatch

The detector does not connect to the operating system running inside the
instance.

It does not require:

- SSH access
- SSM access
- Instance credentials
- Guest operating-system credentials
- CloudWatch Agent installation

The current rule uses standard EC2 CloudWatch metrics only.

Memory utilization is not collected because standard EC2 metrics do not
include memory without an additional agent.

Missing or incomplete CloudWatch data does not cause an instance to be
classified as idle.

## Multi-Region Access

The Lambda can inspect supported resources in every configured
`scan_regions` entry.

For example:

```hcl
scan_regions = [
  "us-east-1",
  "us-east-2",
  "us-west-2",
]
```

The EC2 and CloudWatch read permissions apply when the Lambda creates
regional clients for those scan regions.

Detector-owned state remains centralized in the deployment region.

This means a scan of `us-west-2` can inspect supported resources and
CloudWatch metrics there while writing its finding state to the detector
DynamoDB table in the home region.

## DynamoDB Security

The detector stores finding lifecycle information in Amazon DynamoDB.

The table can contain information such as:

- Resource identifiers
- Resource ARNs
- AWS region
- Finding status
- Finding timestamps
- Estimated savings
- Priority information
- Notification state
- Detector metadata used to explain findings

Idle EC2 finding metadata can include utilization values such as CPU,
network activity, metric coverage, instance type, and launch time.

Server-side encryption is enabled.

Point-in-time recovery is enabled by default in the Terraform
configuration.

Optional deletion protection is available.

The Lambda role is limited to the DynamoDB operations required by the
detector, such as reading and updating finding records.

## S3 Report Security

HTML reports are stored in a detector-owned Amazon S3 bucket.

The bucket is configured with public access blocked.

The detector does not make reports publicly readable.

Bucket-owner-enforced object ownership is used.

Server-side encryption is enabled for stored report objects.

Reports are automatically expired according to the configured retention
period.

Example:

```hcl
report_retention_days = 30
```

Reports may contain AWS resource identifiers, regions, recommendations,
utilization-derived findings, and estimated savings.

Access to the report bucket should therefore be limited to intended
users and administrators.

## Presigned URLs

The detector generates temporary S3 presigned URLs for report access.

A presigned URL grants temporary access to the specific report object
without making the bucket public.

Treat a presigned URL as a temporary credential.

Do not:

- Commit it to Git
- Publish it in documentation
- Post it in public issue trackers
- Include it in public logs or screenshots
- Store it permanently

If a URL expires, generate a new report or otherwise create a new
temporary access URL rather than changing the bucket to public access.

## SNS Security

Amazon SNS is used for detector notifications.

The Lambda can publish only through the detector's configured SNS topic
according to its Terraform-managed IAM policy.

Email subscriptions require the recipient to confirm the subscription
before notifications are delivered.

Notifications can contain resource information, AWS regions, finding
details, and estimated savings, so notification recipients should be
limited to intended users.

## CloudWatch Security

CloudWatch is used in two distinct ways.

### Detector Logs and Alarms

Lambda execution logs are written to the detector CloudWatch log group.

Logs may contain operational information such as:

- Scan regions
- Finding processing results
- Persistence results
- Resolution results
- Report object locations

Application code should avoid logging:

- AWS secret access keys
- Session tokens
- Presigned report URLs
- Other credentials

The detector logs the report S3 bucket and object key rather than the
presigned URL.

Terraform also configures CloudWatch alarms for Lambda errors and
throttling.

### EC2 Utilization Metrics

Idle EC2 detection reads standard metrics from CloudWatch using
`cloudwatch:GetMetricData`.

The current metrics include:

```text
AWS/EC2 CPUUtilization
AWS/EC2 NetworkIn
AWS/EC2 NetworkOut
```

These metrics are read only for classification and are not modified by
the detector.

## Terraform Configuration

`terraform.tfvars` can contain deployment-specific information such as:

- Notification email address
- Region configuration
- Environment selection
- Resource naming
- Idle EC2 thresholds
- Lambda timeout

The file is intentionally ignored by Git.

Do not commit a real `terraform.tfvars` file to a public repository.

Use:

```text
infrastructure/terraform.tfvars.example
```

as the public configuration template.

The example file should contain only placeholder or non-sensitive
example values.

## Lambda Environment Variables

The Lambda receives detector configuration through environment
variables, including values such as:

```text
WASTE_FINDINGS_TABLE
COST_WASTE_ALERTS_TOPIC_ARN
FINDING_GRACE_PERIOD_DAYS
REPORT_BUCKET
SCAN_REGIONS
EC2_IDLE_LOOKBACK_DAYS
EC2_IDLE_AVERAGE_CPU_THRESHOLD_PERCENT
EC2_IDLE_MAXIMUM_CPU_THRESHOLD_PERCENT
EC2_IDLE_NETWORK_IN_THRESHOLD_MIB
EC2_IDLE_NETWORK_OUT_THRESHOLD_MIB
EC2_IDLE_MINIMUM_METRIC_COVERAGE
```

These values identify detector resources and configuration.

They should not contain AWS access keys or other long-lived secrets.

AWS provides `AWS_REGION` to the Lambda runtime.

The application validates the Idle EC2 configuration at runtime so an
invalid out-of-band Lambda environment change fails instead of silently
changing detector behavior.

## Pricing API

The detector uses the AWS Pricing API to obtain pricing information used
for savings estimates.

Pricing access is read-only.

The detector does not send customer AWS credentials to a third-party
pricing service.

Current pricing reads are used for EBS, public IPv4, and supported
On-Demand EC2 compute estimates.

## Customer Resource Modification

The current detector is advisory.

It identifies potential waste and provides recommendations.

It does not automatically:

- Delete EBS volumes
- Release Elastic IP addresses
- Stop or terminate EC2 instances
- Change resource configurations
- Modify networking
- Remediate findings

This limits the impact of a detector error or incorrect recommendation.

Users should independently review a finding before changing or deleting
a resource.

## Regional Failure Handling

A failure in one configured scan region currently fails the overall
Lambda invocation.

This behavior is intentional because silently generating a successful
partial report could hide an incomplete scan.

Lambda execution failures are visible through CloudWatch metrics and the
detector's configured alarms.

## Data Residency

Detector state and reports are stored in the configured deployment
region.

Resource metadata and utilization metrics are retrieved from configured
scan regions during execution and processed by the Lambda.

For example:

```text
us-east-2 EC2 metadata + CloudWatch metrics
        |
        v
Lambda in us-east-1
        |
        +--> DynamoDB in us-east-1
        |
        +--> S3 in us-east-1
```

Users with data-residency requirements should consider both the selected
deployment region and configured scan regions before deployment.

## Encryption

Detector-owned persistent storage uses AWS-managed encryption features.

Current controls include:

- DynamoDB server-side encryption
- S3 server-side encryption

AWS service API calls are made through the AWS SDK using normal AWS
service endpoints.

Organizations with additional encryption requirements can extend the
Terraform configuration to use customer-managed AWS KMS keys.

## DynamoDB Deletion Protection

Deletion protection is optional.

For environments where preserving finding history is important, enable:

```hcl
dynamodb_deletion_protection_enabled = true
```

This reduces the risk of accidentally deleting the findings table during
infrastructure changes.

It must be disabled before intentionally destroying the table.

## Report Retention

Reports should not be retained indefinitely unless required.

The S3 lifecycle configuration automatically removes old reports after
the configured period.

Example:

```hcl
report_retention_days = 30
```

This limits the amount of historical resource information retained in
S3.

## Notification Deduplication

The detector stores notification state with findings.

A finding that has already triggered its eligible notification is not
intended to generate the same alert on every scheduled scan.

This reduces unnecessary exposure of repeated resource information and
avoids notification flooding.

## Operational Monitoring

Terraform configures CloudWatch alarms for:

- Lambda execution errors
- Lambda throttling

These alarms publish through the detector SNS topic.

Operational alarms help surface failures that could otherwise result in
missing or incomplete cost-waste scans.

## Shared Responsibility

The detector reduces the permissions it needs, but the deploying
customer remains responsible for:

- Securing the AWS account
- Protecting Terraform credentials
- Controlling access to the AWS console
- Managing SNS subscribers
- Managing access to CloudWatch logs and metrics
- Managing access to DynamoDB data
- Reviewing IAM changes before Terraform apply
- Reviewing findings before remediation
- Selecting appropriate deployment and scan regions

## Recommended Deployment Practices

Before deploying to a production AWS account:

- Review the Terraform plan
- Review the Lambda IAM policy
- Use a non-root AWS identity
- Enable MFA for administrative AWS identities
- Keep `terraform.tfvars` out of source control
- Limit access to detector reports
- Confirm only intended SNS subscribers
- Consider enabling DynamoDB deletion protection
- Retain CloudWatch logs according to organizational requirements
- Review findings before manually modifying resources

## Current Security Boundary

The current model can be summarized as:

```text
Customer AWS account
        |
        +--> read supported customer resources
        |
        +--> read supported CloudWatch utilization metrics
        |
        +--> write detector-owned state
        |
        +--> write detector-owned reports
        |
        +--> publish detector notifications
        |
        +--> no automatic customer-resource remediation
```

The current project supports one AWS account per deployment.

Future multi-account or hosted deployments would require additional
trust boundaries and should use dedicated cross-account IAM roles rather
than sharing long-lived AWS credentials.
