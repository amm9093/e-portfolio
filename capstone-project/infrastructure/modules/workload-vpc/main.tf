# Three-AZ clinical network (report: "Terraform implementation", Snippet 2).
# Wraps the widely used community VPC module, pinned to a major version.

module "vpc" {
  # checkov:skip=CKV_TF_1:Registry module pinned by version; .terraform.lock.hcl records provider hashes. Mirror privately before production (Report risk R4).
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = var.name
  cidr = var.cidr
  azs  = var.azs

  private_subnets  = var.private_subnets
  database_subnets = var.database_subnets
  public_subnets   = var.public_subnets

  create_database_subnet_group = true

  # One NAT gateway per AZ: costs more than one shared gateway, but losing
  # an AZ does not cut the other two off from the internet.
  enable_nat_gateway     = true
  single_nat_gateway     = var.single_nat_gateway
  one_nat_gateway_per_az = !var.single_nat_gateway

  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC flow logs: the network evidence trail DSPT assessors ask for.
  enable_flow_log                                 = true
  create_flow_log_cloudwatch_log_group            = true
  create_flow_log_cloudwatch_iam_role             = true
  flow_log_max_aggregation_interval               = 60
  flow_log_cloudwatch_log_group_retention_in_days = var.flow_log_retention_days
  flow_log_cloudwatch_log_group_kms_key_id        = var.kms_key_arn

  # Lock down the default security group so nothing can use it by accident.
  manage_default_security_group  = true
  default_security_group_ingress = []
  default_security_group_egress  = []
}

# Gateway endpoint: traffic to S3 (e.g. the imaging archive) stays on the
# AWS network and does not pass through the NAT gateways (cheaper and safer).
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = {
    Name = "${var.name}-s3"
  }
}

data "aws_region" "current" {}
