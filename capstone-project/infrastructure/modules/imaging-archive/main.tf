# Ransomware-resistant archive for medical images (report: "Terraform implementation", Snippet 3).
# Object Lock in COMPLIANCE mode means no one - including an administrator -
# can delete or overwrite an object version until its retention period ends.

resource "aws_s3_bucket" "this" {
  # checkov:skip=CKV_AWS_144:Cross-region copies are made by AWS Backup (report: "Regulatory landscape"), not S3 replication.
  # checkov:skip=CKV_AWS_18:Access logs are captured by CloudTrail S3 data events in the log-archive account.
  # checkov:skip=CKV2_AWS_62:Event notifications are not needed for an archive bucket.
  bucket              = "${var.name_prefix}-imaging-archive"
  object_lock_enabled = true
  force_destroy       = false
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled" # required by Object Lock
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    object_ownership = "BucketOwnerEnforced" # disables ACLs entirely
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true # reduces KMS request costs
  }
}

resource "aws_s3_bucket_object_lock_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.retention_days
    }
  }
  depends_on = [aws_s3_bucket_versioning.this]
}

# Images move to cheaper storage as they age. Nothing is expired here:
# NHS retention periods vary by patient, so deletion is driven by the
# records-management system, not by a lifecycle rule.
resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    id     = "tier-by-age"
    status = "Enabled"
    filter {}

    transition {
      days          = var.glacier_ir_after_days
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = var.deep_archive_after_days
      storage_class = "DEEP_ARCHIVE"
    }
  }

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

# Reject any request that is not encrypted in transit.
data "aws_iam_policy_document" "tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.this.arn,
      "${aws_s3_bucket.this.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket     = aws_s3_bucket.this.id
  policy     = data.aws_iam_policy_document.tls_only.json
  depends_on = [aws_s3_bucket_public_access_block.this]
}
