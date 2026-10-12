# Meridian-specific policy checks on a Terraform plan (report: "The delivery pipeline and its validation", step 4).
# Run with conftest against the JSON form of a plan:
#   terraform plan -out=tfplan
#   terraform show -json tfplan > plan.json
#   conftest test --policy policies/opa plan.json

package main

import rego.v1

# Resources that are created or updated (deletes have no "after" state).
changed contains rc if {
	some rc in input.resource_changes
	some action in rc.change.actions
	action in {"create", "update"}
}

# Rule 1: S3 buckets must be encrypted with KMS, not the default S3-managed key.
deny contains msg if {
	some rc in changed
	rc.type == "aws_s3_bucket_server_side_encryption_configuration"
	some rule in rc.change.after.rule
	some enc in rule.apply_server_side_encryption_by_default
	enc.sse_algorithm != "aws:kms"
	msg := sprintf("%s: S3 encryption must use aws:kms with a customer-managed key", [rc.address])
}

# Rule 2: databases must be encrypted with a customer-managed key.
deny contains msg if {
	some rc in changed
	rc.type == "aws_rds_cluster"
	not rc.change.after.storage_encrypted
	msg := sprintf("%s: storage_encrypted must be true", [rc.address])
}

deny contains msg if {
	some rc in changed
	rc.type == "aws_rds_cluster"
	not has_kms_key(rc)
	msg := sprintf("%s: kms_key_id must reference a customer-managed key", [rc.address])
}

# The key ARN is often unknown until apply; "known after apply" counts as set.
has_kms_key(rc) if rc.change.after.kms_key_id != null

has_kms_key(rc) if rc.change.after_unknown.kms_key_id == true

# Rule 3: data stores must carry a data classification tag.
data_stores := {"aws_s3_bucket", "aws_rds_cluster", "aws_kms_key", "aws_backup_vault"}

deny contains msg if {
	some rc in changed
	rc.type in data_stores
	not rc.change.after.tags_all.data_class
	msg := sprintf("%s: missing data_class tag", [rc.address])
}

# Rule 4: nothing may be opened to the whole internet except HTTPS.
deny contains msg if {
	some rc in changed
	rc.type == "aws_vpc_security_group_ingress_rule"
	rc.change.after.cidr_ipv4 == "0.0.0.0/0"
	rc.change.after.from_port != 443
	msg := sprintf("%s: only port 443 may be open to 0.0.0.0/0", [rc.address])
}
