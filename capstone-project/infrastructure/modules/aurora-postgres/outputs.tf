output "writer_endpoint" {
  description = "Endpoint for writes."
  value       = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  description = "Load-balanced endpoint for read replicas."
  value       = aws_rds_cluster.this.reader_endpoint
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN holding the master credentials."
  value       = aws_rds_cluster.this.master_user_secret[0].secret_arn
}
