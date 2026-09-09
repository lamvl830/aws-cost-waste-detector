# Configure the AWS provider used to create our infrastructure.
#
# Credentials are intentionally NOT stored here.
# Terraform will use the AWS profile supplied through the
# AWS_PROFILE environment variable.
provider "aws" {
  region = "us-east-1"
}