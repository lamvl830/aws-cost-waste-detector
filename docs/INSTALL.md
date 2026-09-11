# AWS Cost Waste Detector — Installation

AWS Cost Waste Detector is a self-hosted FinOps scanner that runs inside
your own AWS account.

The detector currently identifies:

- Unattached EBS volumes
- Unused Elastic IP addresses

It estimates potential monthly savings using live AWS pricing, stores
finding history in DynamoDB, generates private HTML reports in S3, and
can send notifications through Amazon SNS.

The detector does not automatically delete or modify the AWS resources
it evaluates.

## Architecture

The deployment creates resources in your AWS account including:

- AWS Lambda for running scans
- Amazon DynamoDB for finding history
- Amazon S3 for private HTML reports
- Amazon SNS for notifications
- Amazon EventBridge Scheduler for automatic scans
- Amazon CloudWatch Logs and alarms
- IAM roles and policies required by the detector

## Prerequisites

Before deploying, install:

- Terraform 1.5 or newer
- AWS CLI v2
- Git

You must also have AWS credentials with permission to create the
resources defined by the Terraform configuration.

Verify your AWS authentication before deploying:

```bash
aws sts get-caller-identity