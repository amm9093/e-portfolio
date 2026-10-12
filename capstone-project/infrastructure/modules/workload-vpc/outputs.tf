output "vpc_id" {
  description = "ID of the VPC."
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Application subnet IDs."
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Load balancer subnet IDs."
  value       = module.vpc.public_subnets
}

output "database_subnet_group_name" {
  description = "Name of the database subnet group."
  value       = module.vpc.database_subnet_group_name
}

output "private_route_table_ids" {
  description = "Private route table IDs (used by the network hub for return routes)."
  value       = module.vpc.private_route_table_ids
}
