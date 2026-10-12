# Unit tests for terraform.rego. Run with:
#   conftest verify --policy policies/opa

package main

import rego.v1

compliant_plan := {"resource_changes": [
	{
		"address": "module.imaging_archive.aws_s3_bucket_server_side_encryption_configuration.this",
		"type": "aws_s3_bucket_server_side_encryption_configuration",
		"change": {
			"actions": ["create"],
			"after": {"rule": [{"apply_server_side_encryption_by_default": [{"sse_algorithm": "aws:kms"}]}]},
		},
	},
	{
		"address": "module.epr_database.aws_rds_cluster.this",
		"type": "aws_rds_cluster",
		"change": {
			"actions": ["create"],
			"after": {"storage_encrypted": true, "kms_key_id": null, "tags_all": {"data_class": "patient-identifiable"}},
			"after_unknown": {"kms_key_id": true},
		},
	},
	{
		"address": "module.patient_portal.aws_vpc_security_group_ingress_rule.alb_https",
		"type": "aws_vpc_security_group_ingress_rule",
		"change": {
			"actions": ["create"],
			"after": {"cidr_ipv4": "0.0.0.0/0", "from_port": 443},
		},
	},
]}

non_compliant_plan := {"resource_changes": [
	{
		"address": "aws_s3_bucket_server_side_encryption_configuration.bad",
		"type": "aws_s3_bucket_server_side_encryption_configuration",
		"change": {
			"actions": ["create"],
			"after": {"rule": [{"apply_server_side_encryption_by_default": [{"sse_algorithm": "AES256"}]}]},
		},
	},
	{
		"address": "aws_rds_cluster.bad",
		"type": "aws_rds_cluster",
		"change": {
			"actions": ["create"],
			"after": {"storage_encrypted": false, "kms_key_id": null, "tags_all": {}},
			"after_unknown": {},
		},
	},
	{
		"address": "aws_vpc_security_group_ingress_rule.ssh",
		"type": "aws_vpc_security_group_ingress_rule",
		"change": {
			"actions": ["create"],
			"after": {"cidr_ipv4": "0.0.0.0/0", "from_port": 22},
		},
	},
]}

# Positive test: a compliant plan produces no denials.
test_compliant_plan_passes if {
	count(deny) == 0 with input as compliant_plan
}

# Negative tests: each violation is caught.
test_s3_without_kms_is_denied if {
	some msg in deny with input as non_compliant_plan
	contains(msg, "aws_s3_bucket_server_side_encryption_configuration.bad")
}

test_unencrypted_database_is_denied if {
	some msg in deny with input as non_compliant_plan
	contains(msg, "storage_encrypted must be true")
}

test_database_without_key_is_denied if {
	some msg in deny with input as non_compliant_plan
	contains(msg, "kms_key_id must reference")
}

test_missing_classification_tag_is_denied if {
	some msg in deny with input as non_compliant_plan
	contains(msg, "missing data_class tag")
}

test_ssh_open_to_internet_is_denied if {
	some msg in deny with input as non_compliant_plan
	contains(msg, "only port 443")
}

# Exception test: deleted resources are ignored (they have no "after" state).
test_deletes_are_ignored if {
	count(deny) == 0 with input as {"resource_changes": [{
		"address": "aws_rds_cluster.old",
		"type": "aws_rds_cluster",
		"change": {"actions": ["delete"], "after": null},
	}]}
}
