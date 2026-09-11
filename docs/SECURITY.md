# Security Model

AWS Cost Waste Detector is designed to run entirely inside the
customer's AWS account.

The project does not require customers to provide AWS access keys to
the application or to any external service.

## Execution model

The detector runs as an AWS Lambda function using an IAM execution
role created by Terraform.

AWS supplies temporary credentials to Lambda automatically through
that role.

The detector currently scans:

- Amazon EBS volumes
- Elastic IP addresses

It reads AWS pricing data, persists finding history, generates private
HTML reports, and publishes notifications.

## Read-only access to customer resources

The detector only requires read access to the AWS resources it scans.

Current EC2 permissions:

```text
ec2:DescribeVolumes
ec2:DescribeAddresses