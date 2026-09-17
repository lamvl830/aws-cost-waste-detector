# Changelog

All notable changes to AWS Cost Waste Detector are documented here.

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