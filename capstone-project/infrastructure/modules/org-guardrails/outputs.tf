output "policy_id" {
  description = "ID of the guardrails service control policy."
  value       = aws_organizations_policy.guardrails.id
}
