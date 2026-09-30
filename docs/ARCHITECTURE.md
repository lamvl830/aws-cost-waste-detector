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
      │ EC2 + CW    │     │ EC2 + CW    │     │ EC2 + CW    │
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
- CloudWatch logs and alarms

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

For EC2 idle detection, CloudWatch utilization metrics are queried in
the same region as the EC2 instance being evaluated.

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

This distinction is important because AWS resources and their
utilization telemetry are inspected regionally, while detector state
remains centralized.

## Detector Engine

Each regional scan runs through the same detector engine.

Its main responsibilities are:

1. Determine the AWS account identity.
2. Create regional AWS service clients.
3. Scan supported resources.
4. Collect utilization metrics when required by a detector.
5. Build normalized findings.
6. Estimate potential savings.
7. Load active findings for that account and region.
8. Persist new or existing findings.
9. Apply lifecycle rules.
10. Reconcile findings that are no longer present.
11. Calculate finding priority.
12. Send eligible finding notifications.
13. Return regional results to the Lambda handler.

The Lambda handler aggregates the results from all configured regions.

## Regional AWS Clients

Resource APIs are called in the target scan region.

For example:

```text
scan region = us-east-2
        |
        +--> EC2 client in us-east-2
        |      |
        |      +--> DescribeVolumes
        |      +--> DescribeAddresses
        |      +--> DescribeInstances
        |
        +--> CloudWatch client in us-east-2
               |
               +--> GetMetricData
```

This ensures resources and telemetry are evaluated in the region where
they actually exist.

The AWS Pricing API is handled separately and uses the pricing service
endpoint required by the implementation.

Pricing calculations still use the resource region when selecting
applicable pricing information.

## Idle EC2 Data Flow

Idle EC2 detection adds a utilization-analysis path to the existing
resource-discovery architecture.

```text
DescribeInstances
      |
      v
running On-Demand instances
      |
      +--> skip Spot instances
      |
      +--> skip instances younger than lookback window
      |
      v
CloudWatch GetMetricData
      |
      +--> CPUUtilization / Average
      +--> CPUUtilization / Maximum
      +--> NetworkIn / Sum
      +--> NetworkOut / Sum
      |
      v
validate metric coverage
      |
      v
compare utilization to configured thresholds
      |
      +--> active / insufficient data --> no finding
      |
      v
EC2_IDLE finding
      |
      v
AWS Pricing API
      |
      v
estimated monthly compute savings
```

The idle rule is intentionally fail-safe. Missing required metrics or
insufficient metric coverage do not cause an instance to be classified
as idle.

The rule currently uses standard EC2 CloudWatch metrics only. Memory
utilization is outside the current architecture because it requires an
additional agent on customer instances.

## CloudWatch Metric Abstraction

CloudWatch metric access is isolated behind a reusable metric-query
helper.

The helper:

- accepts normalized metric query definitions
- builds `GetMetricData` requests
- handles pagination
- returns normalized numeric series
- rejects duplicate internal query identifiers

This keeps EC2 idle classification independent from the raw CloudWatch
API response format.

The same abstraction can be reused by future utilization-based detectors
such as oversized EC2 or idle RDS detection.

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

For example, a single EC2 instance can eventually have independent
findings such as:

```text
EC2_IDLE
EC2_OVERSIZED
```

without changing the finding identity model.

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

Reconciliation is also scoped to rules that were successfully evaluated
during the scan. This prevents unrelated or unevaluated rule findings
from being incorrectly resolved.

## Cost Estimation

Pricing providers are kept separate from scanner logic.

Current pricing paths include:

```text
EBS finding
    |
    +--> EBS pricing provider

EIP finding
    |
    +--> public IPv4 pricing provider

EC2_IDLE finding
    |
    +--> EC2 On-Demand pricing provider
```

For Idle EC2 findings, the pricing provider derives an hourly On-Demand
compute price from instance type, operating system, tenancy, and resource
region.

The current monthly EC2 estimate uses approximately 730 hours per month.

Pricing failures do not prevent the idle condition itself from being
identified; an unpriced idle finding can still be emitted with zero
estimated savings.

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

Supported finding types can include direct AWS Console links. Idle EC2
findings link to the associated EC2 instance details page.

## Notifications

There are two notification paths.

### Finding Notifications

Eligible HIGH or CRITICAL findings can be notified during the regional
scan.

Because they are emitted from the regional detector result, the
originating AWS region remains associated with the finding.

Notification state is stored with the finding so a successfully notified
finding is not repeatedly sent on every scan.

### Consolidated Report Notification

After all regions are complete, the Lambda can send one summary
notification for the combined result.

This avoids sending a separate daily report email for every region.

Zero-finding runs still generate an HTML report but do not send a report
summary notification.

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
- Read EC2 utilization metrics from CloudWatch
- Read pricing information
- Read and write detector-owned DynamoDB state
- Publish to the detector SNS topic
- Write and retrieve detector reports in S3
- Write CloudWatch logs

For the current scanners, the resource-observation permissions include:

```text
ec2:DescribeVolumes
ec2:DescribeAddresses
ec2:DescribeInstances
cloudwatch:GetMetricData
pricing:GetProducts
```

It does not receive permissions to automatically:

- Delete EBS volumes
- Release Elastic IP addresses
- Stop EC2 instances
- Terminate EC2 instances
- Modify customer workloads

EC2 `Describe` actions and CloudWatch metric-read actions generally
require wildcard resources because these APIs do not support useful
resource-level IAM restrictions for this access pattern.

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
    |       +--> regional CloudWatch metrics
    |       +--> pricing lookup
    |       +--> lifecycle processing
    |       +--> DynamoDB in deployment region
    |
    +--> scan us-east-2
    |       |
    |       +--> regional EC2 APIs
    |       +--> regional CloudWatch metrics
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

The tradeoff is longer execution time as more regions or
utilization-based resources are added.

CloudWatch metric queries increase the amount of API work performed per
eligible EC2 instance, so execution duration can grow with both the
number of regions and the number of running instances.

The Lambda timeout is configurable to provide deployment-specific
headroom.

If the supported region count or resource count grows significantly,
parallel regional execution or batched metric collection may become
useful.

### Conservative Idle Classification

Idle EC2 classification requires multiple independent signals rather
than relying on average CPU alone.

This reduces false positives caused by:

- short CPU bursts hidden by a low average
- network-heavy workloads with little CPU usage
- incomplete CloudWatch telemetry
- newly launched instances with an incomplete observation window

The tradeoff is that some potentially idle instances may be intentionally
left unreported.

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
Regional CloudWatch utilization reads
Centralized finding persistence
Consolidated reporting
Read-only customer-resource analysis
```

Multi-account and AWS Organizations support are outside the current
architecture and would require an additional account-access model.

Automated remediation is also outside the current architecture. The
detector produces recommendations and findings but does not stop,
terminate, delete, or otherwise modify customer workloads.
