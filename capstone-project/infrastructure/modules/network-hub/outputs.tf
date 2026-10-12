output "transit_gateway_id" {
  description = "ID of the Transit Gateway hub."
  value       = aws_ec2_transit_gateway.this.id
}

output "vpn_connection_ids" {
  description = "VPN connection IDs, by site."
  value       = { for k, v in aws_vpn_connection.hospital : k => v.id }
}
