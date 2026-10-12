variable "name" {
  description = "Service name, e.g. prod-patient-portal. Used for the cluster, service and load balancer."
  type        = string
}

variable "vpc_id" {
  description = "VPC to deploy into."
  type        = string
}

variable "private_subnet_ids" {
  description = "Subnets for the application tasks (one per AZ)."
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Subnets for the load balancer (one per AZ)."
  type        = list(string)
}

variable "container_image" {
  description = "Container image URI, ideally from Amazon ECR and pinned by digest."
  type        = string
}

variable "container_port" {
  description = "Port the container listens on."
  type        = number
  default     = 8080
}

variable "cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 512
}

variable "memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "cpu_architecture" {
  description = "ARM64 (Graviton, cheaper) or X86_64."
  type        = string
  default     = "ARM64"

  validation {
    condition     = contains(["ARM64", "X86_64"], var.cpu_architecture)
    error_message = "cpu_architecture must be ARM64 or X86_64."
  }
}

variable "min_tasks" {
  description = "Minimum running tasks. Keep at least 3 in production (one per AZ)."
  type        = number
  default     = 3
}

variable "max_tasks" {
  description = "Maximum running tasks: the cost ceiling."
  type        = number
  default     = 30

  validation {
    condition     = var.max_tasks <= 50
    error_message = "max_tasks above 50 needs a reviewed change to this validation rule (cost control)."
  }
}

variable "cpu_target" {
  description = "Average CPU percentage that auto scaling aims to hold."
  type        = number
  default     = 60
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the HTTPS listener."
  type        = string
}

variable "ingress_cidr_blocks" {
  description = "CIDR ranges allowed to reach the load balancer on 443. In production, use the CloudFront origin-facing ranges."
  type        = list(string)
  default     = []
}

variable "health_check_path" {
  description = "Path the load balancer checks for a healthy response."
  type        = string
  default     = "/health"
}

variable "kms_key_arn" {
  description = "KMS key ARN for encrypting the log group."
  type        = string
}

variable "log_retention_days" {
  description = "How long to keep application logs."
  type        = number
  default     = 365
}

variable "deletion_protection" {
  description = "Protect the load balancer from accidental deletion."
  type        = bool
  default     = true
}

variable "task_role_policy_arns" {
  description = "IAM policy ARNs the application needs. Empty by default (least privilege)."
  type        = list(string)
  default     = []
}
