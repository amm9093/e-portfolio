# Hub-and-spoke network linking the hospitals to AWS (report: "Target architecture" and "Hybrid cloud").
# Transit Gateway connects each workload VPC. Hospitals connect over two
# Direct Connect links, with an encrypted Site-to-Site VPN as fail-over.
#
# Note: Direct Connect circuits are physical lines ordered from a provider.
# This module creates the AWS side (the Direct Connect gateway) once the
# circuits exist; set enable_direct_connect = true at that point.

resource "aws_ec2_transit_gateway" "this" {
  description                     = "${var.name} hub"
  amazon_side_asn                 = var.amazon_side_asn
  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  dns_support                     = "enable"
  vpn_ecmp_support                = "enable"
  auto_accept_shared_attachments  = "disable"

  tags = {
    Name = "${var.name}-tgw"
  }
}

# One attachment per workload VPC (the "spokes").
resource "aws_ec2_transit_gateway_vpc_attachment" "spokes" {
  for_each = var.spoke_vpcs

  transit_gateway_id = aws_ec2_transit_gateway.this.id
  vpc_id             = each.value.vpc_id
  subnet_ids         = each.value.subnet_ids

  tags = {
    Name = "${var.name}-${each.key}"
  }
}

# Return routes: send hospital-bound traffic from each spoke to the hub.
resource "aws_route" "spoke_to_onsite" {
  for_each = {
    for pair in flatten([
      for spoke_key, spoke in var.spoke_vpcs : [
        for idx, rt in spoke.route_table_ids : [
          for cidr in var.onsite_cidrs : {
            # Keys use the list position, not the route table ID, because IDs
            # are unknown until the VPC exists and for_each keys must be known.
            key   = "${spoke_key}-${idx}-${cidr}"
            rt    = rt
            cidr  = cidr
            spoke = spoke_key
          }
        ]
      ]
    ]) : pair.key => pair
  }

  route_table_id         = each.value.rt
  destination_cidr_block = each.value.cidr
  transit_gateway_id     = aws_ec2_transit_gateway.this.id

  depends_on = [aws_ec2_transit_gateway_vpc_attachment.spokes]
}

# ---------------------------------------------------------------- Direct Connect
resource "aws_dx_gateway" "this" {
  count           = var.enable_direct_connect ? 1 : 0
  name            = "${var.name}-dxgw"
  amazon_side_asn = var.dx_gateway_asn
}

resource "aws_dx_gateway_association" "this" {
  count                 = var.enable_direct_connect ? 1 : 0
  dx_gateway_id         = aws_dx_gateway.this[0].id
  associated_gateway_id = aws_ec2_transit_gateway.this.id
  allowed_prefixes      = var.aws_prefixes_advertised_onsite
}

# ---------------------------------------------------------------- VPN fail-over
resource "aws_customer_gateway" "hospital" {
  for_each   = var.vpn_sites
  bgp_asn    = each.value.bgp_asn
  ip_address = each.value.public_ip
  type       = "ipsec.1"

  tags = {
    Name = "${var.name}-${each.key}"
  }
}

resource "aws_vpn_connection" "hospital" {
  for_each            = var.vpn_sites
  customer_gateway_id = aws_customer_gateway.hospital[each.key].id
  transit_gateway_id  = aws_ec2_transit_gateway.this.id
  type                = "ipsec.1"
  static_routes_only  = false # BGP, so routes fail over automatically

  tags = {
    Name = "${var.name}-${each.key}-vpn"
  }
}
