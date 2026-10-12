variable "name_prefix" {
  description = "Prefix for the policy name, e.g. meridian."
  type        = string
}

variable "approved_regions" {
  description = "Regions where regional services may be used. London for primary data; Ireland for encrypted backups only."
  type        = list(string)
  default     = ["eu-west-2", "eu-west-1"]
}

variable "target_ids" {
  description = "Organisational unit (ou-...) or account IDs to attach the guardrails to, e.g. the Workloads OU."
  type        = list(string)
}
