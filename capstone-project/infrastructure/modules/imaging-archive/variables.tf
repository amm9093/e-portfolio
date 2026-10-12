variable "name_prefix" {
  description = "Prefix for the bucket name, e.g. meridian-prod. Bucket names are global, so make it unique."
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the customer-managed KMS key used to encrypt images."
  type        = string
}

variable "retention_days" {
  description = "Object Lock COMPLIANCE retention in days. Cannot be shortened once objects are written."
  type        = number
  default     = 35

  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 3650
    error_message = "retention_days must be between 1 and 3650."
  }
}

variable "glacier_ir_after_days" {
  description = "Days before images move to Glacier Instant Retrieval."
  type        = number
  default     = 90
}

variable "deep_archive_after_days" {
  description = "Days before images move to Glacier Deep Archive."
  type        = number
  default     = 1095

  validation {
    condition     = var.deep_archive_after_days >= 180
    error_message = "deep_archive_after_days should be at least 180 to avoid early-deletion charges."
  }
}
