variable "name" {
  description = "Cluster name, e.g. prod-epr."
  type        = string
}

variable "vpc_id" {
  description = "VPC the database runs in."
  type        = string
}

variable "db_subnet_group_name" {
  description = "Database subnet group spanning three AZs."
  type        = string
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect on 5432 (e.g. the application tasks)."
  type        = list(string)
  default     = []
}

variable "engine_version" {
  description = "Aurora PostgreSQL version. Check the versions currently supported in your region before use."
  type        = string
  default     = "16.4"
}

variable "database_name" {
  description = "Initial database name."
  type        = string
  default     = "epr"
}

variable "master_username" {
  description = "Master user name. The password is managed by Secrets Manager."
  type        = string
  default     = "epr_admin"
}

variable "instance_class" {
  description = "Instance size. Graviton classes (r6g, r7g) cost less."
  type        = string
  default     = "db.r6g.large"
}

variable "instance_count" {
  description = "Number of instances. 3 = one per AZ in production."
  type        = number
  default     = 3

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 15
    error_message = "instance_count must be between 1 and 15."
  }
}

variable "kms_key_arn" {
  description = "Customer-managed KMS key for storage, secrets and Performance Insights."
  type        = string
}

variable "backup_retention_days" {
  description = "Automated backup retention (maximum 35)."
  type        = number
  default     = 35
}

variable "backup_tier" {
  description = "Backup tier tag. \"1\" = tier-1 clinical system, included in the immutable backup plan."
  type        = string
  default     = "1"
}

variable "deletion_protection" {
  description = "Block accidental deletion of the cluster."
  type        = bool
  default     = true
}
