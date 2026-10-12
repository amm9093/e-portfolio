terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Partial configuration: the bucket and key are supplied at init time so no
  # account details are committed. See backend.hcl.example and the README.
  backend "s3" {}
}

# Primary region: all patient data is processed here.
provider "aws" {
  region              = "eu-west-2"
  allowed_account_ids = [var.account_id]

  # Every resource is stamped with ownership and cost tags (report: "Design for scalability, security and cost").
  default_tags {
    tags = {
      owner       = "platform-team"
      environment = var.environment
      cost_centre = var.cost_centre
      data_class  = "patient-identifiable"
      managed_by  = "terraform"
      repository  = "meridian-cloud-strategy"
    }
  }
}

# Disaster-recovery region: encrypted backup copies only (report: "Regulatory landscape").
provider "aws" {
  alias               = "dr"
  region              = "eu-west-1"
  allowed_account_ids = [var.account_id]

  default_tags {
    tags = {
      owner       = "platform-team"
      environment = var.environment
      cost_centre = var.cost_centre
      data_class  = "patient-identifiable"
      managed_by  = "terraform"
      repository  = "meridian-cloud-strategy"
    }
  }
}
