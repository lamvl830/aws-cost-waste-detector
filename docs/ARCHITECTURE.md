# Architecture

AWS Cost Waste Detector is a self-hosted FinOps scanner that runs
entirely inside the customer's AWS account.

Version 0.1 currently detects:

- Unattached Amazon EBS volumes
- Unused Elastic IP addresses

It estimates potential savings using live AWS pricing, persists finding
history, generates private HTML reports, and sends notifications for
important findings and detector health issues.

## High-level architecture

```text
                    ┌─────────────────────────┐
                    │ EventBridge Scheduler   │
                    │     rate(1 day)         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │       AWS Lambda        │
                    │   Cost Waste Detector   │
                    └────────────┬────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             │                   │                   │
             ▼                   ▼                   ▼
      ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
      │    EC2      │     │ AWS Pricing │     │  DynamoDB   │
      │  EBS / EIP  │     │     API     │     │  Findings   │
      └─────────────┘     └─────────────┘     └─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Finding prioritization  │
                    │ lifecycle + savings     │
                    └────────────┬────────────┘
                                 │
                     ┌───────────┴───────────┐
                     │                       │
                     ▼                       ▼
              ┌─────────────┐         ┌─────────────┐
              │     S3      │         │     SNS     │
              │ HTML report │         │   Alerts    │
              └─────────────┘         └─────────────┘
                                             ▲
                                             │
                                    ┌────────┴────────┐
                                    │ CloudWatch      │
                                    │ Errors/Throttle │
                                    └─────────────────┘