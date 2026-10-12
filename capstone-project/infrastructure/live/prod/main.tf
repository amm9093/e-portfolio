# Production environment for Meridian Health Group.
# This file only wires modules together with production inputs; all resource
# logic lives in ../../modules, so non-production is built from the same code.

locals {
  name = "${var.org_prefix}-${var.environment}"
}

# Account-wide backstop: no S3 bucket in this account can ever be made public.
resource "aws_s3_account_public_access_block" "this" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

module "clinical_vpc" {
  source = "../../modules/workload-vpc"

  name               = "${var.environment}-clinical"
  cidr               = "10.20.0.0/16"
  single_nat_gateway = false # one NAT per AZ in production
  kms_key_arn        = aws_kms_key.phi.arn
}

module "network_hub" {
  source = "../../modules/network-hub"

  name = var.environment
  spoke_vpcs = {
    clinical = {
      vpc_id          = module.clinical_vpc.vpc_id
      subnet_ids      = module.clinical_vpc.private_subnet_ids
      route_table_ids = module.clinical_vpc.private_route_table_ids
    }
  }
  onsite_cidrs          = var.onsite_cidrs
  enable_direct_connect = var.enable_direct_connect
  vpn_sites             = var.vpn_sites
}

module "imaging_archive" {
  source = "../../modules/imaging-archive"

  name_prefix    = local.name
  kms_key_arn    = aws_kms_key.phi.arn
  retention_days = 35
}

module "patient_portal" {
  source = "../../modules/ecs-service"

  name                = "${var.environment}-patient-portal"
  vpc_id              = module.clinical_vpc.vpc_id
  private_subnet_ids  = module.clinical_vpc.private_subnet_ids
  public_subnet_ids   = module.clinical_vpc.public_subnet_ids
  container_image     = var.portal_image
  certificate_arn     = var.portal_certificate_arn
  ingress_cidr_blocks = var.portal_ingress_cidrs
  kms_key_arn         = aws_kms_key.phi.arn

  min_tasks  = 3  # one per AZ
  max_tasks  = 30 # cost ceiling
  cpu_target = 60
}

module "epr_database" {
  source = "../../modules/aurora-postgres"

  name                       = "${var.environment}-epr"
  vpc_id                     = module.clinical_vpc.vpc_id
  db_subnet_group_name       = module.clinical_vpc.database_subnet_group_name
  allowed_security_group_ids = [module.patient_portal.app_security_group_id]
  kms_key_arn                = aws_kms_key.phi.arn
  instance_count             = 3
}
