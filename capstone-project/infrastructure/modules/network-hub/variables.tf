variable "name" {
  description = "Name prefix, e.g. prod."
  type        = string
}

variable "amazon_side_asn" {
  description = "Private BGP ASN for the Transit Gateway."
  type        = number
  default     = 64512
}

variable "spoke_vpcs" {
  description = "Workload VPCs to attach. Key = short name."
  type = map(object({
    vpc_id          = string
    subnet_ids      = list(string)
    route_table_ids = list(string)
  }))
  default = {}
}

variable "onsite_cidrs" {
  description = "Hospital network ranges reachable through the hub."
  type        = list(string)
  default     = ["10.0.0.0/12"]
}

variable "enable_direct_connect" {
  description = "Create the Direct Connect gateway. Set true once the physical circuits are provisioned."
  type        = bool
  default     = false
}

variable "dx_gateway_asn" {
  description = "Private BGP ASN for the Direct Connect gateway."
  type        = number
  default     = 64513
}

variable "aws_prefixes_advertised_onsite" {
  description = "AWS CIDR ranges advertised to the hospitals over Direct Connect."
  type        = list(string)
  default     = ["10.20.0.0/16"]
}

variable "vpn_sites" {
  description = "Hospital sites with a VPN fail-over link. Key = site name."
  type = map(object({
    public_ip = string
    bgp_asn   = number
  }))
  default = {}
}
