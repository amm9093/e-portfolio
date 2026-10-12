variable "account_id" {
  description = "AWS account ID for production. Terraform refuses to run against any other account."
  type        = string
}

variable "org_prefix" {
  description = "Short organisation prefix used in resource names."
  type        = string
  default     = "meridian"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "prod"
}

variable "cost_centre" {
  description = "Cost centre code for FinOps reporting."
  type        = string
  default     = "IT-PLATFORM"
}

variable "onsite_cidrs" {
  description = "Hospital network ranges."
  type        = list(string)
  default     = ["10.0.0.0/12"]
}

variable "enable_direct_connect" {
  description = "Set true once the Direct Connect circuits are provisioned."
  type        = bool
  default     = false
}

variable "vpn_sites" {
  description = "Hospital sites with VPN fail-over."
  type = map(object({
    public_ip = string
    bgp_asn   = number
  }))
  default = {}
}

variable "portal_image" {
  description = "Container image for the patient portal (ARM64)."
  type        = string
}

variable "portal_certificate_arn" {
  description = "ACM certificate ARN for the portal's HTTPS listener."
  type        = string
}

variable "portal_ingress_cidrs" {
  description = "Ranges allowed to reach the portal load balancer."
  type        = list(string)
  default     = []
}
