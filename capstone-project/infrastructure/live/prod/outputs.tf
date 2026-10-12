output "vpc_id" {
  value = module.clinical_vpc.vpc_id
}

output "portal_load_balancer" {
  value = module.patient_portal.alb_dns_name
}

output "imaging_archive_bucket" {
  value = module.imaging_archive.bucket_id
}

output "epr_writer_endpoint" {
  value = module.epr_database.writer_endpoint
}

output "transit_gateway_id" {
  value = module.network_hub.transit_gateway_id
}
