# Unit tests for the imaging-archive module (Report Appendix B).
# A mock provider means these run with NO AWS account and NO cost:
#   cd infrastructure/modules/imaging-archive
#   terraform init
#   terraform test

mock_provider "aws" {
  # The bucket policy is built from a data source; give it valid JSON.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

variables {
  name_prefix = "meridian-test"
  kms_key_arn = "arn:aws:kms:eu-west-2:111122223333:key/00000000-0000-0000-0000-000000000000"
}

# Positive test: the secure defaults are applied.
run "bucket_is_locked_encrypted_and_private" {
  command = plan

  assert {
    condition     = aws_s3_bucket.this.object_lock_enabled == true
    error_message = "Object Lock must be enabled on the imaging archive."
  }

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.this.rule[0].default_retention[0].mode == "COMPLIANCE"
    error_message = "Object Lock must use COMPLIANCE mode so nobody can override it."
  }

  assert {
    condition     = one([for r in aws_s3_bucket_server_side_encryption_configuration.this.rule : one(r.apply_server_side_encryption_by_default).sse_algorithm]) == "aws:kms"
    error_message = "Images must be encrypted with a customer-managed KMS key."
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.this.block_public_acls,
      aws_s3_bucket_public_access_block.this.block_public_policy,
      aws_s3_bucket_public_access_block.this.ignore_public_acls,
      aws_s3_bucket_public_access_block.this.restrict_public_buckets,
    ])
    error_message = "All four public access block settings must be true."
  }
}

# Positive test: storage tiering is configured.
run "lifecycle_tiers_images_by_age" {
  command = plan

  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.this.rule) == 2
    error_message = "Expected a tiering rule and an incomplete-upload rule."
  }
}

# Negative test: an invalid retention period is rejected.
run "rejects_zero_retention" {
  command = plan

  variables {
    retention_days = 0
  }

  expect_failures = [var.retention_days]
}

# Negative test: moving to Deep Archive too early is rejected.
run "rejects_early_deep_archive" {
  command = plan

  variables {
    deep_archive_after_days = 30
  }

  expect_failures = [var.deep_archive_after_days]
}
