# Architecture

AWS Cost Waste Detector is a self-hosted FinOps scanner that runs
entirely inside the customer's AWS account.

The architecture is designed around a centralized control plane in one
AWS region with resource scanning across multiple configured regions.

For installation, usage, configuration, supported detectors, and
user-facing behavior, see the main [README](../README.md).

## High-Level Architecture

```text
                    ┌─────────────────────────┐
                    │ EventBridge Scheduler   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │       AWS Lambda        │
                    │   Cost Waste Detector   │
                    │                         │
                    │   Deployment Region     │
                    └────────────┬────────────┘
                                 │
                          SCAN_REGIONS
                                 │
             ┌───────────────────┼───────────────────┐
             │                   │                   │
             ▼                   ▼                   ▼
      ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
      │ us-east-1   │     │ us-east-2   │     │ us-west-2   │
      │ EBS / EIP   │     │ EBS / EIP   │     │ EBS / EIP   │
      └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Aggregate Findings      │
                    │ lifecycle + priority    │
                    │ + cost estimates        │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
      ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
      │  DynamoDB   │    │     S3      │    │     SNS     │
      │  Findings   │    │ HTML Report │    │   Alerts    │
      └─────────────┘    └─────────────┘    └─────────────┘
```

## Regional Model

The architecture separates two concepts:

```text
Deployment region
    = where detector infrastructure lives

Scan region
    = where customer resources are inspected
```

### Deployment Region

`aws_region` defines the detector's home region.

Resources such as the following remain centralized there:

- AWS Lambda
- Amazon DynamoDB
- Amazon S3
- Amazon SNS
- EventBridge Scheduler
- CloudWatch resources

For example:

```hcl
aws_region = "us-east-1"
```

### Scan Regions

`scan_regions` defines the regions whose supported resources are
inspected.

Example:

```hcl
scan_regions = [
  "us-east-1",
  "us-east-2",
  "us-west-2",
]
```

If `scan_regions` is omitted, the detector scans only `aws_region`.

This preserves the original single-region behavior while allowing
multi-region scanning without duplicating the detector infrastructure in
every region.

## Scan Execution

EventBridge invokes one Lambda function.

That Lambda processes every configured scan region within the same
invocation.

```text
Lambda invocation
      |
      +--> scan us-east-1
      |
      +--> scan us-east-2
      |
      +--> scan us-west-2
      |
      v
aggregate findings
      |
      v
generate one consolidated report
```

The current implementation scans regions sequentially.

For each region, the Lambda calls the detector engine with:

```text
region         = resource scan region
storage_region = deployment region
```

This distinction is important because AWS resources are inspected
regionally, while detector state remains centralized.

## Detector Engine

Each regional scan runs through the same detector engine.

Its main responsibilities are:

1. Determine the AWS account identity.
2. Create regional AWS service clients.
3. Scan supported resources.
4. Build normalized findings.
5. Estimate potential savings.
6. Load active findings for that account and region.
7. Persist new or existing findings.
8. Apply lifecycle rules.
9. Reconcile findings that are no longer present.
10. Calculate finding priority.
11. Send eligible finding notifications.
12. Return regional results to the Lambda handler.

The Lambda handler aggregates the results from all configured regions.

## Regional AWS Clients

Resource APIs are called in the target scan region.

For example:

```text
scan region = us-east-2
        |
        +--> EC2 client in us-east-2
        |
        +--> DescribeVolumes
        |
        +--> DescribeAddresses
```

This ensures resources are evaluated in the region where they actually
exist.

The AWS Pricing API is handled separately and uses the pricing service
endpoint required by the implementation.

Pricing calculations still use the resource region when selecting
applicable pricing information.

## Centralized State

DynamoDB remains in the deployment region.

```text
Scan us-east-1 ──┐
                 │
Scan us-east-2 ──┼──> DynamoDB in deployment region
                 │
Scan us-west-2 ──┘
```

This provides one central finding history for the entire deployment and
avoids creating a separate state store in every scan region.

## Finding Identity

Findings are stored using a resource/rule identity:

```text
PK = RESOURCE#{resource_arn}
SK = RULE#{rule_id}
```

This allows:

- Multiple rules to apply to one resource
- Existing findings to be updated rather than duplicated
- Historical lifecycle state to be preserved
- Findings from different regions to remain distinct

Each finding also stores its AWS region explicitly.

## Region-Scoped Reconciliation

Reconciliation must remain scoped to the region currently being scanned.

For example:

```text
Scan us-east-1
      |
      +--> compare against active us-east-1 findings

Scan us-east-2
      |
      +--> compare against active us-east-2 findings
```

A resource missing from `us-east-2` must not cause a finding from
`us-east-1` to be marked resolved.

This is especially important because all regional findings share the same
DynamoDB table.

## Reporting

After all regions have been scanned, the Lambda aggregates their current
findings into one consolidated summary.

```text
regional findings
      |
      v
combined finding list
      |
      v
combined cost summary
      |
      v
one HTML report
```

Single-region report keys use the resource region:

```text
reports/<account-id>/<region>/cost-waste-report-<timestamp>.html
```

Multi-region runs use:

```text
reports/<account-id>/multi-region/cost-waste-report-<timestamp>.html
```

The S3 bucket remains in the deployment region.

## Notifications

There are two notification paths.

### Finding Notifications

Eligible HIGH or CRITICAL findings can be notified during the regional
scan.

Because they are emitted from the regional detector result, the
originating AWS region remains associated with the finding.

### Consolidated Report Notification

After all regions are complete, the Lambda can send one summary
notification for the combined result.

This avoids sending a separate daily report email for every region.

## Failure Behavior

The current design treats a regional scan failure as a failure of the
overall Lambda invocation.

For example:

```text
us-east-1 succeeds
us-east-2 fails
        |
        v
Lambda invocation fails
```

This is intentional.

Silently producing a partial report could make the detector appear
healthy while omitting one or more regions.

A failed invocation is instead surfaced through Lambda error metrics and
CloudWatch alarms.

A future version could support explicit partial-success reporting if that
behavior becomes desirable.

## IAM Boundary

The detector uses read-oriented permissions for customer resources.

It can:

- Describe supported EC2 resources
- Read pricing information
- Read and write detector-owned DynamoDB state
- Publish to the detector SNS topic
- Write and retrieve detector reports in S3
- Write CloudWatch logs

It does not receive permissions to automatically:

- Delete EBS volumes
- Release Elastic IP addresses
- Terminate EC2 instances
- Modify customer workloads

EC2 `Describe` actions generally require wildcard resources because those
APIs do not support resource-level IAM restrictions in the same way many
write APIs do.

Detector-owned resources are restricted to the deployment resources
created by Terraform where practical.

## Multi-Region Data Flow

A two-region execution looks like this:

```text
EventBridge
    |
    v
Lambda in deployment region
    |
    +--> scan us-east-1
    |       |
    |       +--> regional EC2 APIs
    |       +--> pricing lookup
    |       +--> lifecycle processing
    |       +--> DynamoDB in deployment region
    |
    +--> scan us-east-2
    |       |
    |       +--> regional EC2 APIs
    |       +--> pricing lookup
    |       +--> lifecycle processing
    |       +--> DynamoDB in deployment region
    |
    v
aggregate current findings
    |
    +--> consolidated cost summary
    |
    +--> consolidated HTML report
    |
    +--> S3 in deployment region
    |
    +--> optional SNS report notification
```

## Design Tradeoffs

### Centralized Infrastructure

Keeping Lambda, DynamoDB, S3, and SNS in one deployment region keeps the
deployment model simple and avoids duplicating infrastructure.

The tradeoff is that scans of other regions make cross-region API calls
back to centralized detector services.

### Sequential Region Scanning

Regions are currently processed sequentially.

Advantages:

- Simple execution model
- Easier error handling
- Easier logging and debugging
- Lower implementation complexity

The tradeoff is longer execution time as more regions are added.

If the supported region count grows significantly, parallel regional
execution may become useful.

### One Consolidated Report

The detector creates one report per Lambda invocation instead of one
report per region.

Advantages:

- One place to review account-wide findings
- One summary notification
- Easier comparison across regions
- Less report fragmentation

The tradeoff is that the report represents the whole scan run rather
than an isolated regional result.

## Architecture Boundaries

The current architecture supports:

```text
1 AWS account per deployment
Multiple AWS regions per deployment
Centralized detector infrastructure
Region-scoped resource scanning
Centralized finding persistence
Consolidated reporting
```

Multi-account and AWS Organizations support are outside the current
architecture and would require an additional account-access model.