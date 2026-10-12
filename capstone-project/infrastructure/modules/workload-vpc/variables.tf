variable "name" {
  description = "Name of the VPC, e.g. prod-clinical."
  type        = string
}

variable "cidr" {
  description = "VPC CIDR block. Must not overlap the hospital networks."
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability Zones to span. Three are recommended for clinical workloads."
  type        = list(string)
  default     = ["eu-west-2a", "eu-west-2b", "eu-west-2c"]
}

variable "private_subnets" {
  description = "Application subnets, one per AZ."
  type        = list(string)
  default     = ["10.20.0.0/20", "10.20.16.0/20", "10.20.32.0/20"]
}

variable "database_subnets" {
  description = "Database subnets, one per AZ."
  type        = list(string)
  default     = ["10.20.48.0/24", "10.20.49.0/24", "10.20.50.0/24"]
}

variable "public_subnets" {
  description = "Load balancer subnets, one per AZ."
  type        = list(string)
  default     = ["10.20.64.0/24", "10.20.65.0/24", "10.20.66.0/24"]
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway. Set true for non-production to save cost; keep false for production."
  type        = bool
  default     = false
}

variable "kms_key_arn" {
  description = "KMS key ARN for encrypting the flow log group. The key policy must allow CloudWatch Logs."
  type        = string
}

variable "flow_log_retention_days" {
  description = "How long to keep VPC flow logs."
  type        = number
  default     = 365
}
