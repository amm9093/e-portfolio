# Organisation-level guardrails. Apply from the AWS Organizations
# management account only, through the pipeline's management role.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region              = "eu-west-2"
  allowed_account_ids = [var.management_account_id]

  default_tags {
    tags = {
      owner      = "platform-team"
      managed_by = "terraform"
      repository = "meridian-cloud-strategy"
    }
  }
}

variable "management_account_id" {
  description = "AWS Organizations management account ID."
  type        = string
}

variable "workloads_ou_id" {
  description = "ID of the Workloads organisational unit (ou-xxxx-xxxxxxxx)."
  type        = string
}

variable "sandbox_ou_id" {
  description = "ID of the Sandbox organisational unit."
  type        = string
}

module "guardrails" {
  source = "../../modules/org-guardrails"

  name_prefix      = "meridian"
  approved_regions = ["eu-west-2", "eu-west-1"]
  target_ids       = [var.workloads_ou_id, var.sandbox_ou_id]
}

output "guardrails_policy_id" {
  value = module.guardrails.policy_id
}
