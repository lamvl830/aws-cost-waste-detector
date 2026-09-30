# Changelog

All notable changes to AWS Cost Waste Detector are documented here.

## [0.3.0] - 2026-09-30

### Added

- Idle On-Demand EC2 instance detection
- CloudWatch utilization analysis using CPU and network metrics
- Configurable Idle EC2 lookback period and utilization thresholds
- Minimum CloudWatch metric-coverage requirement for idle classification
- Live EC2 On-Demand pricing and estimated monthly compute savings
- EC2 instance discovery across configured scan regions
- Direct AWS Console links for Idle EC2 findings
- Reusable CloudWatch metric-query helper
- Detector-level orchestration tests for Idle EC2
- Lambda configuration tests for Idle EC2 environment settings

### Changed

- Lambda IAM permissions now include `ec2:DescribeInstances` and
  `cloudwatch:GetMetricData`
- Lambda timeout is configurable and defaults to 180 seconds
- EC2 utilization metrics are queried in the region where each instance runs
- Idle EC2 classification fails safe when required metrics are missing or
  metric coverage is insufficient
- HTML reports display `Region(s)` for single-region and multi-region scans
- Documentation updated for Idle EC2 detection, CloudWatch metrics, pricing,
  configuration, architecture, and security
- Automated test suite expanded to 149 tests

## [0.2.0] - 2026-09-17

### Added

- Multi-region AWS resource scanning
- Configurable `scan_regions` Terraform setting
- Centralized finding persistence across scan regions
- Consolidated multi-region HTML reports
- Multi-region S3 report paths
- Region parsing and multi-region orchestration tests

### Changed

- Detector now separates resource scan regions from the infrastructure
  deployment region
- Findings from multiple regions are aggregated into one cost summary
- Documentation updated for the multi-region architecture

## [0.1.0]

### Added

- Unattached EBS volume detection
- Unused Elastic IP detection
- Live AWS Pricing API integration
- Estimated monthly and annual savings
- Finding lifecycle tracking
- Priority scoring
- DynamoDB persistence
- HIGH and CRITICAL SNS finding notifications
- Private HTML reports in Amazon S3
- Presigned report URLs
- EventBridge scheduled scans
- CloudWatch error and throttling alarms
- Terraform deployment